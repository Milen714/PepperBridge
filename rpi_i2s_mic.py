# -*- coding: utf-8 -*-
import struct
import threading
import pyaudio


class I2SMicrophone(object):
    def __init__(
        self,
        sample_rate=16000,
        chunk_size=512,
        device_index=None,
        gain=2.0,
    ):
        """
        Captures 32-bit stereo audio from an INMP441 on adau7002-simple,
        extracts the Left channel, removes DC offset, and returns 16-bit mono PCM.
        """
        self.sample_rate = int(sample_rate)
        self.chunk_size = int(chunk_size)
        self.gain = float(gain)

        self.pa = pyaudio.PyAudio()
        self.device_index = (
            device_index if device_index is not None else self._find_i2s_device()
        )
        self.stream = None

        self._prev_raw = 0.0
        self._prev_filtered = 0.0
        self._unpack_fmt = "<{0}i".format(self.chunk_size * 2)
        self._pack_fmt = "<{0}h".format(self.chunk_size)
        self._expected_bytes = self.chunk_size * 2 * 4  # 2 ch * 4 bytes (paInt32)

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

    def _find_i2s_device(self):
        preferred = ("i2smic", "default", "adau7002", "googlevoi", "i2s")
        for keyword in preferred:
            for i in range(self.pa.get_device_count()):
                dev_info = self.pa.get_device_info_by_index(i)
                name = dev_info.get("name", "").lower()
                if keyword in name and dev_info.get("maxInputChannels", 0) > 0:
                    return i
        return None

    def start(self):
        """Opens the 32-bit stereo PortAudio input stream."""
        if self.pa is None:
            self.pa = pyaudio.PyAudio()
        if self.stream is not None:
            return

        self._prev_raw = 0.0
        self._prev_filtered = 0.0
        self.stream = self.pa.open(
            format=pyaudio.paInt32,
            channels=2,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk_size,
        )

    def read_chunk(self):
        """
        Reads one chunk from the mic and returns 16-bit mono PCM bytes
        (chunk_size * 2 bytes), or None on error.
        """
        if not self.stream:
            return None

        try:
            raw_bytes = self.stream.read(
                self.chunk_size, exception_on_overflow=False
            )
        except IOError as e:
            print("Audio buffer error: " + str(e))
            return None

        if len(raw_bytes) < self._expected_bytes:
            return None

        raw_samples = struct.unpack(self._unpack_fmt, raw_bytes)
        pcm_samples = []
        prev_raw = self._prev_raw
        prev_filtered = self._prev_filtered
        gain = self.gain

        # Take Left channel only (even indices) to exclude the unused Right slot
        for raw_val in raw_samples[0::2]:
            sample = raw_val / 65536.0
            filtered = sample - prev_raw + 0.995 * prev_filtered
            prev_raw = sample
            prev_filtered = filtered

            amplified = int(filtered * gain)
            if amplified > 32767:
                amplified = 32767
            elif amplified < -32768:
                amplified = -32768
            pcm_samples.append(amplified)

        self._prev_raw = prev_raw
        self._prev_filtered = prev_filtered
        return struct.pack(self._pack_fmt, *pcm_samples)

    def start_microphone_recording(self, on_audio, on_end=None):
        """
        PepperBridge-compatible streaming wrapper.
        Calls on_audio(pcm_bytes) continuously in a background thread.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self.start()
            self._thread = threading.Thread(
                target=self._stream_loop, args=(on_audio, on_end)
            )
            self._thread.daemon = True
            self._thread.start()

    def _stream_loop(self, on_audio, on_end):
        try:
            while not self._stop_event.is_set():
                pcm_bytes = self.read_chunk()
                if pcm_bytes is None:
                    break
                if on_audio is not None:
                    on_audio(pcm_bytes)
        finally:
            self._close_stream()
            if on_end is not None:
                on_end()

    def _close_stream(self):
        with self._lock:
            stream = self.stream
            self.stream = None
        if stream is not None:
            try:
                stream.stop_stream()
            except IOError:
                pass
            try:
                stream.close()
            except IOError:
                pass

    def stop(self):
        """Stops streaming and closes the input stream (safe to restart later)."""
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._close_stream()

    def close(self):
        """Stops streaming and terminates the underlying PortAudio instance."""
        self.stop()
        if self.pa is not None:
            self.pa.terminate()
            self.pa = None


if __name__ == "__main__":
    import wave

    mic = I2SMicrophone(sample_rate=16000, chunk_size=512, gain=2.0)
    print ("Using PortAudio device index:", mic.device_index)

    mic.start()
    frames = []
    print ("Recording 3 seconds...")
    try:
        # 16000 Hz / 512 samples per chunk ~= 31 chunks per second
        for _ in range(94):
            pcm_bytes = mic.read_chunk()
            if pcm_bytes:
                frames.append(pcm_bytes)
    except KeyboardInterrupt:
        pass
    finally:
        mic.close()

    wf = wave.open("pyaudio_test.wav", "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)  # 16-bit PCM
    wf.setframerate(16000)
    wf.writeframes("".join(frames))
    wf.close()
    print ("Saved pyaudio_test.wav")