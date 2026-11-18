"""UDP peer discovery: periodic presence broadcast, listener, and 10s timeout reaper."""

from __future__ import annotations

from collections.abc import Callable
import socket
import threading
import time

from protocol import (
    BROADCAST_INTERVAL,
    DEFAULT_BCAST,
    PEER_TIMEOUT,
    UDP_PORT,
    VALID_STATUSES,
    PeerInfo,
    decode_hello,
    encode_hello,
)


class UDPDiscovery:
    """Manages UDP broadcast presence announcements and online peer tracking."""

    def __init__(
        self,
        name: str,
        tcp_port: int,
        udp_port: int = UDP_PORT,
        bcast_ip: str = DEFAULT_BCAST,
        on_system: Callable[[str], None] | None = None,
    ) -> None:
        self.name = name.strip()
        self.tcp_port = int(tcp_port)
        self.udp_port = int(udp_port)
        self.bcast_ip = bcast_ip.strip() or DEFAULT_BCAST
        self.on_system = on_system

        self._status = "online"
        self._peers: dict[str, PeerInfo] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._sock: socket.socket | None = None
        self._bcast_thread: threading.Thread | None = None
        self._listen_thread: threading.Thread | None = None

    def _make_socket(self) -> socket.socket:
        """Create and bind a UDP socket configured for broadcast and port sharing."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)
        sock.bind(("", self.udp_port))
        return sock

    def start(self) -> None:
        """Open the UDP socket and start broadcaster and listener daemon threads."""
        if self._sock is not None:
            return
        self._stop_event.clear()
        self._sock = self._make_socket()

        self._listen_thread = threading.Thread(
            target=self._listen_loop, name="udp-listener", daemon=True
        )
        self._bcast_thread = threading.Thread(
            target=self._broadcast_loop, name="udp-broadcaster", daemon=True
        )
        self._listen_thread.start()
        self._bcast_thread.start()

    def stop(self) -> None:
        """Stop discovery threads and close the UDP socket."""
        self._stop_event.set()
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if self._bcast_thread is not None and self._bcast_thread.is_alive():
            self._bcast_thread.join(timeout=1.5)
        if self._listen_thread is not None and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=1.5)

    def set_status(self, status: str) -> None:
        """Update local presence status ('online' or 'away') and broadcast immediately."""
        clean = status.strip().lower()
        if clean not in VALID_STATUSES:
            raise ValueError(f"Status must be one of {VALID_STATUSES}")
        with self._lock:
            self._status = clean
        self._send_presence_once()

    def get_peers(self) -> list[PeerInfo]:
        """Return a snapshot list of currently online peers."""
        with self._lock:
            return [
                PeerInfo(
                    name=p.name,
                    ip=p.ip,
                    tcp_port=p.tcp_port,
                    status=p.status,
                    last_seen=p.last_seen,
                )
                for p in self._peers.values()
            ]

    def resolve_peer(self, target: str) -> PeerInfo | None:
        """Resolve a peer by 1-based list number or by peer name."""
        key = target.strip()
        if not key:
            return None
        peers = self.get_peers()
        if key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(peers):
                return peers[idx]
        for peer in peers:
            if peer.name == key:
                return peer
        for peer in peers:
            if peer.name.lower() == key.lower():
                return peer
        return None

    def _send_presence_once(self) -> None:
        """Send a single UDP HELLO datagram."""
        sock = self._sock
        if sock is None or self._stop_event.is_set():
            return
        with self._lock:
            status = self._status
        try:
            payload = encode_hello(self.name, self.tcp_port, status)
        except ValueError:
            return
        try:
            sock.sendto(payload, (self.bcast_ip, self.udp_port))
        except OSError:
            if self.bcast_ip != "127.255.255.255":
                try:
                    sock.sendto(payload, ("127.255.255.255", self.udp_port))
                except OSError:
                    pass

    def _broadcast_loop(self) -> None:
        """Broadcast presence every BROADCAST_INTERVAL seconds."""
        while not self._stop_event.is_set():
            self._send_presence_once()
            if self._stop_event.wait(BROADCAST_INTERVAL):
                break

    def _listen_loop(self) -> None:
        """Receive UDP presence datagrams and reap timed-out peers."""
        while not self._stop_event.is_set():
            sock = self._sock
            if sock is None:
                break
            try:
                data, addr = sock.recvfrom(1024)
                self._handle_datagram(data, addr[0])
            except socket.timeout:
                pass
            except OSError:
                if self._stop_event.is_set():
                    break
            self._reap_expired_peers()

    def _handle_datagram(self, data: bytes, sender_ip: str) -> None:
        """Parse an incoming HELLO packet and update the online peers table."""
        parsed = decode_hello(data)
        if parsed is None:
            return
        peer_name, peer_tcp_port, peer_status = parsed
        if peer_name == self.name:
            return

        now = time.time()
        notification: str | None = None
        is_new_peer = False
        with self._lock:
            existing = self._peers.get(peer_name)
            if existing is None:
                is_new_peer = True
                self._peers[peer_name] = PeerInfo(
                    name=peer_name,
                    ip=sender_ip,
                    tcp_port=peer_tcp_port,
                    status=peer_status,
                    last_seen=now,
                )
                notification = (
                    f"{peer_name} ({sender_ip}:{peer_tcp_port}) is now {peer_status}"
                )
            else:
                old_status = existing.status
                existing.ip = sender_ip
                existing.tcp_port = peer_tcp_port
                existing.status = peer_status
                existing.last_seen = now
                if old_status != peer_status:
                    notification = f"{peer_name} is now {peer_status}"

        if is_new_peer:
            self._send_presence_once()

        if notification and self.on_system:
            self.on_system(notification)

    def _reap_expired_peers(self) -> None:
        """Remove peers not heard from within PEER_TIMEOUT seconds."""
        now = time.time()
        expired: list[PeerInfo] = []
        with self._lock:
            for name, peer in list(self._peers.items()):
                if now - peer.last_seen > PEER_TIMEOUT:
                    expired.append(self._peers.pop(name))

        if self.on_system:
            for peer in expired:
                self.on_system(f"{peer.name} ({peer.ip}:{peer.tcp_port}) went offline")
