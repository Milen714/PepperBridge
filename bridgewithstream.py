# Python 2.7 NAOqi host. One backend TCP socket, separate ESP32 TCP client.
import logging
import os
import socket
import threading
import traceback
import Queue

from bridge_protocol import send_frame, recv_frame, decode_json
from esp32_audio_client import ESP32AudioClient
from pepper_controller import PepperController

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('PepperBridge')

PLAYBACK_FINISH = object()
PLAYBACK_CANCEL = object()

TYPE_JSON = b'J'
TYPE_PCM = b'P'
TYPE_FINISH = b'F'

class PepperBridge(object):
    def __init__(self, pepper_ip, esp32_ip, host='127.0.0.1', port=9999,
                 esp32_port=50005):
        self.pepper = PepperController(pepper_ip)
        self.mic = ESP32AudioClient(esp32_ip, esp32_port)
        self.host, self.port = host, int(port)
        self.server = None
        self.client = None
        self.write_lock = threading.Lock()
        self.play_buffer = None
        self.play_text = u''
        self.MAX_PLAY_BYTES = 32 * 1024 * 1024

        self.play_queue = None
        self.play_thread = None
        self.play_stop = None
        self.play_error = None
        self.play_sample_rate = None
        self.play_channels = None
        self.play_format = None

    def send(self, kind, payload):
        with self.write_lock:
            if self.client is None:
                return
            send_frame(self.client, kind, payload)

    def on_microphone_audio(self, data):
        try:
            self.send(b'A', data)
        except Exception:
            log.exception('Cannot forward microphone frame')
            self.mic._stop.set()

    def on_microphone_end(self, error):
        try:
            self.send(b'E', {'event': 'recording_stopped', 'error': error})
        except Exception:
            log.exception('Cannot deliver microphone completion')

    def macarena(self):
        try:
            # self.pepper.stop()
            self.pepper.do_macarena()
            self.send(b'J', {'status': 'success'})
        except Exception as exc:
            log.exception('Macarena failed')
            self.send(b'J', {'status': 'error', 'message': str(exc)})

    def command(self, msg):
        command = msg.get('command')
        if command == 'record':
            self.pepper.set_led_state("listening")
            # Reply before audio starts, so the backend knows what follows.
            self.send(b'J', {'status': 'recording_started',
                             'sample_rate': 16000, 'channels': 1, 'format': 's16le'})
            try:
                self.mic.start(self.on_microphone_audio, self.on_microphone_end)
            except Exception as exc:
                self.send(b'E', {'event': 'recording_stopped', 'error': str(exc)})
                self.pepper.set_led_state("idle")
        elif command == 'stop_recording':
            # Do NOT block main reader; on_end sends the recording_stopped event.
            self.mic._stop.set()
            self.mic._close_socket()
        elif command == 'start_audio_stream':
            if self.play_queue is not None:
                self.send(
                    b'J',
                    {
                        'status': 'error',
                        'message': 'Playback already active',
                    },
                )
                return
        
            if (
                msg.get('sample_rate') != 48000
                or msg.get('channels') != 2
                or msg.get('format') != 's16le'
            ):
                self.send(
                    b'J',
                    {
                        'status': 'error',
                        'message': 'Expected 48000 Hz stereo s16le',
                    },
                )
                return
        
            self.play_queue = Queue.Queue()
            self.play_stop = threading.Event()
            self.play_error = None
            self.play_text = msg.get('text', u'')
            self.play_sample_rate = msg.get('sample_rate')
            self.play_channels = msg.get('channels')
            self.play_format = msg.get('format')
        
            self.play_thread = threading.Thread(
                target=self._play_audio_worker,
            )
            self.play_thread.daemon = True
            self.play_thread.start()
        
            self.send(b'J', {'status': 'ready_for_audio'})
        elif command == 'speak':
            try:
                self.pepper.set_led_state("speaking")
                self.pepper.speak(msg.get('target', u''))
                self.send(b'J', {'status': 'success'})
            except Exception as exc:
                log.exception('Speak failed')
                self.send(b'J', {'status': 'error', 'message': str(exc)})

        elif command == "person_present":
            log.info("Checking for person presence...")
            try:
                # present = self.pepper.is_person_present()
                present = True
                log.info("Presence detection result: %s", present)

                self.send(b'J', {
                    'status': 'success',
                    'present': present
                })

            except Exception as exc:
                log.exception("Presence detection failed")
                self.send(b'J', {
                    'status': 'error',
                    'message': str(exc)
                })
        else:
            self.send(b'J', {'status': 'error', 'message': 'Unknown command'})

    def _play_audio_worker(self):
        audio_started = False

        try:
            self.pepper.set_led_state("speaking")

            self.pepper.start_audio_stream(
                sample_rate=self.play_sample_rate,
                channels=self.play_channels,
                audio_format=self.play_format,
            )

            audio_started = True

            while True:
                item = self.play_queue.get()

                if item is PLAYBACK_CANCEL:
                    break

                if item is PLAYBACK_FINISH:
                    self.pepper.finish_audio_stream()
                    break

                self.pepper.write_audio(item)

        except Exception as exc:
            self.play_error = exc
            log.exception('Speaker streaming failed')

            try:
                self.pepper.stop_audio_stream()
            except Exception:
                log.exception('Failed to stop Pepper audio stream')

        finally:
            if audio_started:
                try:
                    self.pepper.stop_audio_stream()
                except Exception:
                    log.exception('Failed to close Pepper audio stream')

    def _reset_audio_stream(self):
        self.play_queue = None
        self.play_thread = None
        self.play_stop = None
        self.play_error = None
        self.play_text = u''
        self.play_sample_rate = None
        self.play_channels = None
        self.play_format = None

    def serve_client(self, client):
        self.client = client
        try:
            while True:
                kind, payload = recv_frame(client)
                if kind == b'J':
                    self.command(decode_json(payload))
                elif kind == b'P':
                    if self.play_queue is None:
                        raise ValueError('Unexpected speaker PCM')

                    if len(payload) % 4:
                        raise ValueError('Speaker PCM is not frame-aligned')

                    if self.play_error is not None:
                        raise ConnectionError(
                            'Speaker playback failed: %s' % self.play_error
                        )

                    self.play_queue.put(payload)
                elif kind == b'F':
                    if self.play_queue is None:
                        raise ValueError('Unexpected playback finish')

                    self.play_queue.put(PLAYBACK_FINISH)

                    if self.play_thread is not None:
                        self.play_thread.join()

                    if self.play_error is not None:
                        error = self.play_error
                        self._reset_audio_stream()
                        self.send(
                            b'J',
                            {
                                'status': 'error',
                                'message': str(error),
                            },
                        )
                    else:
                        self._reset_audio_stream()
                        self.send(
                            b'J',
                            {
                                'status': 'success',
                                'message': 'Audio played',
                            },
                        )
                elif kind == b'X':
                    if self.play_queue is not None:
                        self.play_queue.put(PLAYBACK_CANCEL)

                        if self.play_thread is not None:
                            self.play_thread.join()

                        self._reset_audio_stream()

                    self.send(b'J', {'status': 'success', 'message': 'Audio cancelled'})
                else:
                    raise ValueError('Invalid frame type')
        except (EOFError, socket.error):
            log.info('Backend disconnected')
        except Exception:
            log.exception('Backend connection error')
        finally:
            self.mic.stop()
            self.client = None
            self.play_buffer = None

    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(1)
        log.info('Bridge listening on %s:%s', self.host, self.port)
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

if __name__ == '__main__':
    bridge = PepperBridge(
        # pepper_ip=os.environ.get('PEPPER_IP', '192.168.1.122'),
        pepper_ip=os.environ.get('PEPPER_IP', 'milen.local'), #home
        # esp32_ip=os.environ.get('ESP32_IP', '192.168.1.93'), #alkmaar
        esp32_ip=os.environ.get('ESP32_IP', '192.168.1.17'),    #home
        host=os.environ.get('BRIDGE_HOST', '127.0.0.1'),
        port=int(os.environ.get('BRIDGE_PORT', '9999')),
        esp32_port=int(os.environ.get('ESP32_PORT', '50005'))
    )
    try:
        bridge.start()
        
    except KeyboardInterrupt:
        log.info('Bridge shutting down')
    except Exception:
        log.exception('Bridge failed')
