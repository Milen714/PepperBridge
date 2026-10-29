# Python 2.7 and Python 3 compatible; shared verbatim in both repos.
import json
import struct

HEADER = struct.Struct('!cI')
MAX_FRAME = 1024 * 1024


def recv_exact(sock, size):
    chunks = []
    while size:
        part = sock.recv(size)
        if not part:
            raise EOFError('Peer disconnected')
        chunks.append(part)
        size -= len(part)
    return b''.join(chunks)


def send_frame(sock, kind, payload):
    if isinstance(kind, str):
        kind = kind.encode('ascii')
    if isinstance(payload, dict):
        payload = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    if len(kind) != 1 or len(payload) > MAX_FRAME:
        raise ValueError('Invalid frame')
    sock.sendall(HEADER.pack(kind, len(payload)) + payload)


def recv_frame(sock):
    kind, length = HEADER.unpack(recv_exact(sock, HEADER.size))
    if length > MAX_FRAME:
        raise ValueError('Oversized frame')
    return kind, recv_exact(sock, length)


def decode_json(payload):
    return json.loads(payload.decode('utf-8'))
