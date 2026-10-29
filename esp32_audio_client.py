# Python 2.7. ESP32 TCP server transmits continuous 16kHz mono s16le PCM.
import socket
import threading
import logging
import time

log = logging.getLogger(__name__)

class ESP32AudioClient(object):
    def __init__(self, host, port=50005):
        self.host, self.port = host, int(port)
        self._stop = threading.Event()
        self._thread = None
        self._socket = None

    def start(self, on_audio, on_end):
        if self._thread and self._thread.is_alive():
            raise RuntimeError('Microphone already streaming')
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(on_audio, on_end))
        self._thread.daemon = True
        self._thread.start()

    def _run(self, on_audio, on_end):
        error = None
        try:
            s = socket.create_connection((self.host, self.port), 5.0)
            self._socket = s
            s.settimeout(1.0)
            while not self._stop.is_set():
                try:
                    data = s.recv(4096)
                except socket.timeout:
                    continue
                if not data:
                    raise IOError('ESP32 disconnected')
                on_audio(data)
        except Exception as exc:
            error = str(exc)
            log.exception('ESP32 microphone failed')
        finally:
            self._close_socket()
            on_end(error)

    def _close_socket(self):
        s = self._socket
        self._socket = None
        if s:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except socket.error:
                pass
            s.close()

    def stop(self):
        self._stop.set()
        self._close_socket()
        if self._thread and self._thread != threading.current_thread():
            self._thread.join(3.0)
