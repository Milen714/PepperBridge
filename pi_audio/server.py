import logging
import os
import re
import signal
import socket
import struct
import subprocess
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] pi-audio: %(message)s",
)
log = logging.getLogger("pi-audio")

BIND_HOST = os.environ.get("AUDIO_BIND_HOST", "0.0.0.0")
PORT = int(os.environ.get("AUDIO_PORT", "50005"))
DEVICE_OVERRIDE = os.environ.get("AUDIO_DEVICE", "").strip()
SAMPLE_RATE = int(os.environ.get("SAMPLE_RATE", "16000"))
CHUNK_SAMPLES = int(os.environ.get("CHUNK_SAMPLES", "512"))
MIC_GAIN = float(os.environ.get("MIC_GAIN", "2.0"))
SKIP_INITIAL_CHUNKS = int(os.environ.get("SKIP_INITIAL_CHUNKS", "3"))


def detect_i2s_device():
    if DEVICE_OVERRIDE:
        return DEVICE_OVERRIDE
    try:
        output = subprocess.check_output(
            ["arecord", "-l"], stderr=subprocess.STDOUT, text=True
        )
        for line in output.splitlines():
            lower = line.lower()
            if any(k in lower for k in ("adau7002", "googlevoi", "i2s", "mic")):
                match = re.search(r"card\s+(\d+):", lower)
                if match:
                    return f"plughw:{match.group(1)},0"
    except Exception as exc:
        log.warning("arecord -l failed (%s); falling back to plughw:2,0", exc)
    return "plughw:2,0"


def read_exact(stream, num_bytes):
    chunks = []
    remaining = num_bytes
    while remaining > 0:
        data = stream.read(remaining)
        if not data:
            break
        chunks.append(data)
        remaining -= len(data)
    return b"".join(chunks)


def stream_to_client(conn, addr, device):
    raw_bytes_per_chunk = CHUNK_SAMPLES * 8  # 2 channels * 4 bytes (S32_LE)
    unpack_fmt = f"<{CHUNK_SAMPLES * 2}i"
    pack_fmt = f"<{CHUNK_SAMPLES}h"

    cmd = [
        "arecord",
        "-D", device,
        "-f", "S32_LE",
        "-r", str(SAMPLE_RATE),
        "-c", "2",
        "-t", "raw",
        "-q",
    ]

    log.info("Client %s connected; starting capture on %s", addr, device)
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    conn.settimeout(5.0)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        bufsize=raw_bytes_per_chunk,
    )

    prev_raw = 0.0
    prev_filtered = 0.0
    chunks_seen = 0

    try:
        while True:
            raw_bytes = read_exact(proc.stdout, raw_bytes_per_chunk)
            if len(raw_bytes) < raw_bytes_per_chunk:
                log.warning("arecord stream ended early (rc=%s)", proc.poll())
                break

            raw_samples = struct.unpack(unpack_fmt, raw_bytes)
            pcm_samples = []

            # Left channel only (even indices) to discard the unused Right slot
            for raw_val in raw_samples[0::2]:
                sample = raw_val / 65536.0
                filtered = sample - prev_raw + 0.995 * prev_filtered
                prev_raw = sample
                prev_filtered = filtered

                amplified = int(filtered * MIC_GAIN)
                if amplified > 32767:
                    amplified = 32767
                elif amplified < -32768:
                    amplified = -32768
                pcm_samples.append(amplified)

            # Drop the first ~100 ms so the adau7002 startup pop isn't streamed
            chunks_seen += 1
            if chunks_seen <= SKIP_INITIAL_CHUNKS:
                continue

            conn.sendall(struct.pack(pack_fmt, *pcm_samples))
    except (BrokenPipeError, ConnectionResetError, socket.timeout, OSError) as exc:
        log.info("Client %s disconnected (%s)", addr, exc)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        conn.close()
        log.info("Capture stopped for %s", addr)


def main():
    device = detect_i2s_device()
    log.info(
        "Listening on %s:%d (device=%s, rate=%d Hz, gain=%.1f)",
        BIND_HOST, PORT, device, SAMPLE_RATE, MIC_GAIN,
    )

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((BIND_HOST, PORT))
    srv.listen(1)

    def _handle_sigterm(signum, frame):
        srv.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        while True:
            conn, addr = srv.accept()
            # Re-detect if card index was not overridden
            active_device = detect_i2s_device()
            stream_to_client(conn, addr, active_device)
    except KeyboardInterrupt:
        pass
    finally:
        srv.close()


if __name__ == "__main__":
    main()