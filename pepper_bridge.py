# Python 2.7 NAOqi host. One backend TCP socket, separate ESP32 TCP client.
import logging
import os
import socket
import threading

from bridge_protocol import decode_json, recv_frame, send_frame
from esp32_audio_client import ESP32AudioClient
from pepper_controller import PepperController

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("PepperBridge")

TYPE_JSON = b"J"
TYPE_PCM = b"P"
TYPE_FINISH = b"F"


class PepperBridge:
    def __init__(
        self, pepper_ip, esp32_ip, host="127.0.0.1", port=9999, esp32_port=50005
    ):
        self.pepper = PepperController(pepper_ip)
        self.mic = ESP32AudioClient(esp32_ip, esp32_port)
        self.host, self.port = host, int(port)
        self.server = None
        self.client = None
        self.write_lock = threading.Lock()
        self.play_buffer = None
        self.play_text = ""
        self.MAX_PLAY_BYTES = 32 * 1024 * 1024

    def send(self, kind, payload):
        with self.write_lock:
            if self.client is None:
                return
            send_frame(self.client, kind, payload)

    def on_microphone_audio(self, data):
        try:
            self.send(b"A", data)
        except Exception:
            log.exception("Cannot forward microphone frame")
            self.mic._stop.set()

    def on_microphone_end(self, error):
        try:
            self.send(b"E", {"event": "recording_stopped", "error": error})
        except Exception:
            log.exception("Cannot deliver microphone completion")

    def macarena(self):
        try:
            # self.pepper.stop()
            self.pepper.do_macarena()
            self.send(b"J", {"status": "success"})
        except Exception as exc:
            log.exception("Macarena failed")
            self.send(b"J", {"status": "error", "message": str(exc)})

    def command(self, msg):
        command = msg.get("command")
        if command == "record":
            self.pepper.set_led_state("listening")
            # Reply before audio starts, so the backend knows what follows.
            self.send(
                b"J",
                {
                    "status": "recording_started",
                    "sample_rate": 16000,
                    "channels": 1,
                    "format": "s16le",
                },
            )
            try:
                self.mic.start(self.on_microphone_audio, self.on_microphone_end)
            except Exception as exc:
                self.send(b"E", {"event": "recording_stopped", "error": str(exc)})
                self.pepper.set_led_state("idle")
        elif command == "stop_recording":
            # Do NOT block main reader; on_end sends the recording_stopped event.
            self.mic._stop.set()
            self.mic._close_socket()
        elif command == "stream_audio":
            if self.play_buffer is not None:
                self.send(
                    b"J", {"status": "error", "message": "Playback already active"}
                )
                return
            if (
                msg.get("sample_rate") != 48000
                or msg.get("channels") != 2
                or msg.get("format") != "s16le"
            ):
                self.send(
                    b"J",
                    {"status": "error", "message": "Expected 48000 Hz stereo s16le"},
                )
                return
            self.play_buffer = bytearray()
            self.play_text = msg.get("text", "")
            self.send(b"J", {"status": "ready_for_audio"})
        elif command == "speak":
            try:
                self.pepper.set_led_state("speaking")
                self.pepper.speak(msg.get("target", ""))
                self.send(b"J", {"status": "success"})
            except Exception as exc:
                log.exception("Speak failed")
                self.send(b"J", {"status": "error", "message": str(exc)})
        elif command == "gesture":
            try:
                if self.play_buffer is not None:
                    raise RuntimeError("Cannot gesture while audio is buffered")
                log.info("Executing gesture: %s", msg.get("target"))
                result = self.pepper.execute_animation(msg.get("target"))
                self.send(b"J", result)
            except Exception as exc:
                log.exception("Gesture failed: %s", str(exc))
                self.send(b"J", {"status": "error", "message": str(exc)})

        elif command == "person_present":
            log.info("Checking for person presence...")
            try:
                # present = self.pepper.is_person_present()
                present = True
                log.info("Presence detection result: %s", present)

                self.send(b"J", {"status": "success", "present": present})

            except Exception as exc:
                log.exception("Presence detection failed")
                self.send(b"J", {"status": "error", "message": str(exc)})
        else:
            self.send(b"J", {"status": "error", "message": "Unknown command"})

    def serve_client(self, client):
        self.client = client
        try:
            while True:
                kind, payload = recv_frame(client)
                if kind == b"J":
                    self.command(decode_json(payload))
                elif kind == b"P":
                    if self.play_buffer is None:
                        raise ValueError("Unexpected speaker PCM")
                    if len(self.play_buffer) + len(payload) > self.MAX_PLAY_BYTES:
                        raise ValueError("Speaker PCM exceeds buffer limit")
                    self.play_buffer.extend(payload)
                elif kind == b"F":
                    if self.play_buffer is None:
                        raise ValueError("Unexpected playback finish")
                    samples = bytes(self.play_buffer)
                    text = self.play_text
                    self.play_buffer = None
                    self.play_text = ""
                    try:
                        self.pepper.speak(text, audio_buffer=samples)
                        self.send(
                            b"J", {"status": "success", "message": "Audio played"}
                        )
                    except Exception as exc:
                        log.exception("Speaker playback failed")
                        self.send(b"J", {"status": "error", "message": str(exc)})
                else:
                    raise ValueError("Invalid frame type")
        except (OSError, EOFError):
            log.info("Backend disconnected")
        except Exception:
            log.exception("Backend connection error")
        finally:
            self.mic.stop()
            self.client = None
            self.play_buffer = None

    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(1)
        log.info("Bridge listening on %s:%s", self.host, self.port)
        # self.macarena()
        try:
            while True:
                client, address = self.server.accept()
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.serve_client(client)
                client.close()
        finally:
            self.mic.stop()
            self.server.close()


if __name__ == "__main__":
    bridge = PepperBridge(
        pepper_ip=os.environ.get("PEPPER_IP", "192.168.1.122"),
        # pepper_ip=os.environ.get("PEPPER_IP", "milen.local"),  # home
        esp32_ip=os.environ.get('ESP32_IP', '192.168.1.93'), #alkmaar
        # esp32_ip=os.environ.get('ESP32_IP', '172.27.134.130'), #hotspot
        # esp32_ip=os.environ.get("ESP32_IP", "peppermic.local"),  # .LOCAL
        # esp32_ip=os.environ.get('ESP32_IP', '192.168.1.17'),    #home
        host=os.environ.get("BRIDGE_HOST", "127.0.0.1"),
        port=int(os.environ.get("BRIDGE_PORT", "9999")),
        esp32_port=int(os.environ.get("ESP32_PORT", "50005")),
    )
    try:
        bridge.start()

    except KeyboardInterrupt:
        log.info("Bridge shutting down")
    except Exception:
        log.exception("Bridge failed")
