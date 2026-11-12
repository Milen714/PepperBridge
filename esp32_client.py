# Python 2.7 compatible client for the XIAO ESP32S3 microphone and mmWave
# sensor endpoints. Audio is raw 16 kHz mono s16le PCM over TCP; radar status
# is JSON over HTTP at /radar.
import json
import logging
import socket
import threading

try:
    # Python 2.7
    import urllib2
    from urllib2 import HTTPError, URLError
except ImportError:
    # Python 3, useful for development outside the NAOqi runtime
    import urllib.request as urllib2
    from urllib.error import HTTPError, URLError

log = logging.getLogger(__name__)


class ESP32Client(object):
    """Client for audio streaming and radar presence on one ESP32.

    Args:
        host: ESP32 IP address or hostname.
        audio_port: Firmware PCM TCP port (default 50005).
        http_port: Firmware HTTP port (default 80).
        timeout: Connection/read timeout in seconds.
    """

    def __init__(self, host, port=50005, http_port=80, timeout=5.0,
                 audio_port=None):
        self.host = host
        # ``port`` preserves the original ESP32AudioClient constructor API.
        self.audio_port = int(port if audio_port is None else audio_port)
        self.http_port = int(http_port)
        self.timeout = float(timeout)
        self._stop = threading.Event()
        self._thread = None
        self._socket = None

    def read_radar_status(self):
        """Return the firmware's latest radar JSON as a dictionary.

        Fields currently include status, distance, radarMode, and inRange.
        A failed request or invalid response raises IOError or ValueError.
        """
        url = 'http://%s:%d/radar' % (self.host, self.http_port)
        try:
            response = urllib2.urlopen(url, timeout=self.timeout)
            try:
                payload = response.read()
            finally:
                response.close()
        except (HTTPError, URLError, socket.error) as exc:
            raise IOError('Could not read ESP32 radar status: %s' % exc)

        if not isinstance(payload, str):
            payload = payload.decode('utf-8')
        try:
            status = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid ESP32 radar response: %s' % exc)
        if not isinstance(status, dict) or 'inRange' not in status:
            raise ValueError('ESP32 radar response is missing inRange')
        return status

    def person_present(self):
        """Return True when a target is within the firmware capture zone."""
        return bool(self.read_radar_status().get('inRange', False))

    def start_microphone_recording(self, on_audio, on_end):
        """Start audio streaming on a daemon thread.

        on_audio(bytes) receives PCM chunks. on_end(error) is called once when
        streaming ends; error is None for a requested stop, otherwise a string.
        """
        if self._thread and self._thread.is_alive():
            raise RuntimeError('Microphone already streaming')
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(on_audio, on_end))
        self._thread.daemon = True
        self._thread.start()

    def _run(self, on_audio, on_end):
        error = None
        try:
            sock = socket.create_connection((self.host, self.audio_port), self.timeout)
            self._socket = sock
            sock.settimeout(1.0)
            while not self._stop.is_set():
                try:
                    data = sock.recv(4096)
                except socket.timeout:
                    continue
                if not data:
                    if not self._stop.is_set():
                        raise IOError('ESP32 disconnected')
                    break
                on_audio(data)
        except Exception as exc:
            if not self._stop.is_set():
                error = str(exc)
                log.exception('ESP32 audio stream failed')
        finally:
            self._close_socket()
            on_end(error)

    def _close_socket(self):
        sock = self._socket
        self._socket = None
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except socket.error:
                pass
            sock.close()

    def stop(self):
        """Stop audio streaming; radar reads remain available."""
        self.stop_microphone_recording()
        if self._thread and self._thread != threading.current_thread():
            self._thread.join(3.0)

    def stop_microphone_recording(self):
        """Request microphone stream shutdown without waiting for the worker."""
        self._stop.set()
        self._close_socket()


# Backwards-compatible class name for existing integrations.
ESP32AudioClient = ESP32Client
