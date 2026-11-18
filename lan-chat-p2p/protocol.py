"""Application-layer protocol constants, data structures, and framing helpers."""

from __future__ import annotations

from dataclasses import dataclass
import os
import socket

UDP_PORT = 9999
DEFAULT_TCP_PORT = 5000
DEFAULT_BCAST = "255.255.255.255"
BROADCAST_INTERVAL = 3.0
PEER_TIMEOUT = 10.0
CHUNK_SIZE = 8192
DOWNLOADS_DIR = "downloads"
VALID_STATUSES = ("online", "away")

_MAX_FIELD_BYTES = 1024


@dataclass
class PeerInfo:
    """Information about an online peer discovered via UDP."""

    name: str
    ip: str
    tcp_port: int
    status: str = "online"
    last_seen: float = 0.0


def encode_hello(name: str, tcp_port: int, status: str = "online") -> bytes:
    """Encode a UDP presence datagram: HELLO|<name>|<tcp_port>|<status>."""
    clean_name = name.strip().replace("|", "_")
    clean_status = status.strip().lower()
    if not clean_name:
        raise ValueError("Peer name cannot be empty.")
    if clean_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status {status!r}; expected one of {VALID_STATUSES}.")
    if not (1 <= int(tcp_port) <= 65535):
        raise ValueError(f"Invalid TCP port: {tcp_port}")
    return f"HELLO|{clean_name}|{int(tcp_port)}|{clean_status}".encode("utf-8")


def decode_hello(data: bytes) -> tuple[str, int, str] | None:
    """Decode a UDP presence datagram. Returns (name, tcp_port, status) or None if invalid."""
    try:
        text = data.decode("utf-8", errors="replace").strip()
    except Exception:
        return None
    parts = text.split("|")
    if len(parts) != 4 or parts[0] != "HELLO":
        return None
    name = parts[1].strip()
    status = parts[3].strip().lower()
    if not name or status not in VALID_STATUSES:
        return None
    try:
        tcp_port = int(parts[2].strip())
    except ValueError:
        return None
    if not (1 <= tcp_port <= 65535):
        return None
    return (name, tcp_port, status)


def encode_peer(name: str, tcp_port: int) -> bytes:
    """Encode TCP handshake identification frame: PEER|<name>|<tcp_port>|."""
    clean_name = name.strip().replace("|", "_")
    if not clean_name:
        raise ValueError("Peer name cannot be empty.")
    if not (1 <= int(tcp_port) <= 65535):
        raise ValueError(f"Invalid TCP port: {tcp_port}")
    return f"PEER|{clean_name}|{int(tcp_port)}|".encode("utf-8")


def encode_msg(text: str) -> bytes:
    """Encode a TCP chat message frame: MSG|<byte_length>|<utf-8 bytes>."""
    payload = text.encode("utf-8")
    header = f"MSG|{len(payload)}|".encode("utf-8")
    return header + payload


def encode_file_header(filename: str, size: int) -> bytes:
    """Encode a TCP file transfer header: FILE|<basename>|<size_in_bytes>|."""
    safe_name = os.path.basename(filename.strip()).replace("|", "_")
    if not safe_name:
        raise ValueError("Filename cannot be empty.")
    if int(size) < 0:
        raise ValueError("File size cannot be negative.")
    return f"FILE|{safe_name}|{int(size)}|".encode("utf-8")


def encode_bye() -> bytes:
    """Encode a TCP graceful disconnect frame: BYE|."""
    return b"BYE|"


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from a TCP socket, looping until all bytes arrive."""
    if n < 0:
        raise ValueError("Byte count n must be non-negative.")
    if n == 0:
        return b""
    buf = bytearray()
    while len(buf) < n:
        to_read = min(CHUNK_SIZE, n - len(buf))
        chunk = sock.recv(to_read)
        if not chunk:
            raise ConnectionError(
                f"Connection closed prematurely ({len(buf)}/{n} bytes received)."
            )
        buf.extend(chunk)
    return bytes(buf)


def _read_field(sock: socket.socket, allow_eof_on_first: bool = False) -> str | None:
    """Read a pipe-terminated UTF-8 header field one byte at a time."""
    buf = bytearray()
    while True:
        b = sock.recv(1)
        if not b:
            if allow_eof_on_first and not buf:
                return None
            raise ConnectionError("Connection closed while reading frame header.")
        if allow_eof_on_first and not buf and b in (b"\r", b"\n"):
            # Ignore stray newline between frames (e.g. when testing with netcat)
            continue
        if b == b"|":
            return buf.decode("utf-8", errors="replace")
        buf.extend(b)
        if len(buf) > _MAX_FIELD_BYTES:
            raise ValueError("Frame header field exceeds maximum allowed length.")


def read_frame_header(sock: socket.socket) -> tuple | None:
    """Read and parse the next TCP frame header from sock.

    Returns:
        - None on clean EOF before any frame bytes
        - ("PEER", name: str, tcp_port: int)
        - ("MSG", length: int)
        - ("FILE", filename: str, size: int)
        - ("BYE",)
    """
    frame_type = _read_field(sock, allow_eof_on_first=True)
    if frame_type is None:
        return None
    frame_type = frame_type.strip().upper()

    if frame_type == "BYE":
        return ("BYE",)

    if frame_type == "PEER":
        name_field = _read_field(sock)
        port_field = _read_field(sock)
        assert name_field is not None and port_field is not None
        name = name_field.strip()
        tcp_port = int(port_field.strip())
        if not name or not (1 <= tcp_port <= 65535):
            raise ValueError(f"Invalid PEER frame: {name!r}, {tcp_port}")
        return ("PEER", name, tcp_port)

    if frame_type == "MSG":
        len_field = _read_field(sock)
        assert len_field is not None
        length = int(len_field.strip())
        if length < 0:
            raise ValueError(f"Negative MSG length: {length}")
        return ("MSG", length)

    if frame_type == "FILE":
        name_field = _read_field(sock)
        size_field = _read_field(sock)
        assert name_field is not None and size_field is not None
        safe_name = os.path.basename(name_field.strip())
        size = int(size_field.strip())
        if not safe_name or size < 0:
            raise ValueError(f"Invalid FILE header: {safe_name!r}, {size}")
        return ("FILE", safe_name, size)

    raise ValueError(f"Unknown TCP frame type: {frame_type!r}")
