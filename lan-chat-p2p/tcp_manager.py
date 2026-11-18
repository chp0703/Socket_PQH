"""TCP connection manager: multi-peer chat, unread message tracking, and file transfer."""

from __future__ import annotations

from collections.abc import Callable
import os
import socket
import threading

from protocol import (
    CHUNK_SIZE,
    DOWNLOADS_DIR,
    PeerInfo,
    encode_bye,
    encode_file_header,
    encode_msg,
    encode_peer,
    read_frame_header,
    recv_exact,
)


def _format_size(num_bytes: int) -> str:
    """Format byte size into a human-readable string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


class TCPManager:
    """Manages TCP server acceptor, peer connections, chat histories, unread queues, and file transfers."""

    def __init__(
        self,
        name: str,
        listen_port: int,
        downloads_dir: str = DOWNLOADS_DIR,
        on_chat: Callable[[str, str], None] | None = None,
        on_unread: Callable[[str, int], None] | None = None,
        on_system: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> None:
        self.name = name.strip()
        self.listen_port = int(listen_port)
        self.downloads_dir = downloads_dir
        self.on_chat = on_chat
        self.on_unread = on_unread
        self.on_system = on_system
        self.on_error = on_error
        self.on_progress = on_progress

        self._lock = threading.Lock()
        self._connections: dict[str, socket.socket] = {}
        self._send_locks: dict[str, threading.Lock] = {}
        self._chat_histories: dict[str, list[tuple[str, str]]] = {}
        self._unread_messages: dict[str, list[tuple[str, str]]] = {}
        self._current_partner: str | None = None
        self._file_threads: list[threading.Thread] = []

        self._stop_event = threading.Event()
        self._server_sock: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None

    def start(self) -> None:
        """Bind the TCP listening socket and start the acceptor thread."""
        if self._server_sock is not None:
            return
        os.makedirs(self.downloads_dir, exist_ok=True)
        self._stop_event.clear()

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("", self.listen_port))
        server.listen(16)
        server.settimeout(1.0)
        self._server_sock = server

        self._accept_thread = threading.Thread(
            target=self._accept_loop, name="tcp-acceptor", daemon=True
        )
        self._accept_thread.start()

    def stop(self) -> None:
        """Wait briefly for active file sends, send BYE to all peers, and close sockets."""
        with self._lock:
            active_transfers = [t for t in self._file_threads if t.is_alive()]
        for t in active_transfers:
            t.join(timeout=2.0)

        self._stop_event.set()
        server = self._server_sock
        self._server_sock = None
        if server is not None:
            try:
                server.close()
            except OSError:
                pass

        with self._lock:
            peers_and_socks = list(self._connections.items())
            self._connections.clear()
            self._current_partner = None

        for peer_name, sock in peers_and_socks:
            send_lock = self._send_locks.get(peer_name)
            try:
                if send_lock:
                    with send_lock:
                        sock.sendall(encode_bye())
                else:
                    sock.sendall(encode_bye())
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

        if self._accept_thread is not None and self._accept_thread.is_alive():
            self._accept_thread.join(timeout=1.5)

    def get_current_partner(self) -> str | None:
        """Return the name of the current active chat partner, or None."""
        with self._lock:
            return self._current_partner

    def connect_peer(self, peer: PeerInfo) -> bool:
        """Ensure an active TCP connection exists to the specified peer."""
        with self._lock:
            existing = self._connections.get(peer.name)
            if existing is not None:
                return True

        if peer.tcp_port <= 0:
            if self.on_error:
                self.on_error(f"User '{peer.name}' is not online.")
            return False

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((peer.ip, peer.tcp_port))
            sock.settimeout(None)
            sock.sendall(encode_peer(self.name, self.listen_port))
        except OSError as exc:
            try:
                sock.close()
            except OSError:
                pass
            if self.on_error:
                self.on_error(
                    f"Cannot connect to {peer.name} ({peer.ip}:{peer.tcp_port}): {exc}"
                )
            return False

        with self._lock:
            self._connections[peer.name] = sock
            self._send_locks.setdefault(peer.name, threading.Lock())

        t = threading.Thread(
            target=self._receiver_loop,
            args=(sock, (peer.ip, peer.tcp_port), peer.name),
            name=f"tcp-recv-{peer.name}",
            daemon=True,
        )
        t.start()

        if self.on_system:
            self.on_system(f"Connected to {peer.name} ({peer.ip}:{peer.tcp_port})")
        return True

    def switch_chat(self, peer: PeerInfo) -> list[tuple[str, str]]:
        """Open or switch active chat to peer, returning and clearing any unread messages."""
        with self._lock:
            already_connected = peer.name in self._connections
            unread = list(self._unread_messages.pop(peer.name, []))

        if not already_connected:
            if not self.connect_peer(peer):
                if unread and self.on_system:
                    self.on_system(
                        f"{len(unread)} unread from {peer.name} (peer is now offline):"
                    )
                return unread

        with self._lock:
            self._current_partner = peer.name

        if already_connected and self.on_system:
            if unread:
                self.on_system(f"Switched to {peer.name} — {len(unread)} unread:")
            else:
                self.on_system(
                    f"Switched to {peer.name} ({peer.ip}:{peer.tcp_port})"
                )
        elif unread and self.on_system:
            self.on_system(f"{len(unread)} unread from {peer.name}:")

        return unread

    def leave_chat(self) -> None:
        """Close the current active chat session and return to the main prompt."""
        with self._lock:
            partner = self._current_partner
            if partner is None:
                not_in_chat = True
                sock = None
                send_lock = None
            else:
                not_in_chat = False
                self._current_partner = None
                sock = self._connections.pop(partner, None)
                send_lock = self._send_locks.get(partner)

        if not_in_chat:
            if self.on_error:
                self.on_error("You are not currently in a chat.")
            return

        if sock is not None:
            try:
                if send_lock:
                    with send_lock:
                        sock.sendall(encode_bye())
                else:
                    sock.sendall(encode_bye())
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

        if self.on_system and partner:
            self.on_system(f"Left chat with {partner}.")

    def send_chat(self, text: str) -> bool:
        """Send a chat message to the current chat partner."""
        with self._lock:
            partner = self._current_partner
            sock = self._connections.get(partner) if partner else None
            send_lock = self._send_locks.get(partner) if partner else None

        if not partner or sock is None or send_lock is None:
            if self.on_error:
                self.on_error(
                    "No active chat partner. Use /chat <name|number> first."
                )
            return False

        frame = encode_msg(text)
        try:
            with send_lock:
                sock.sendall(frame)
        except OSError as exc:
            if self.on_error:
                self.on_error(f"Failed to send message to {partner}: {exc}")
            self._cleanup_connection(partner, sock, notify=True)
            return False

        with self._lock:
            self._chat_histories.setdefault(partner, []).append((self.name, text))

        if self.on_chat:
            self.on_chat(self.name, text)
        return True

    def send_file_async(self, filepath: str) -> bool:
        """Start a background thread to send a file to the current chat partner."""
        clean_path = filepath.strip().strip('"').strip("'")
        with self._lock:
            partner = self._current_partner
            sock = self._connections.get(partner) if partner else None
            send_lock = self._send_locks.get(partner) if partner else None

        if not partner or sock is None or send_lock is None:
            if self.on_error:
                self.on_error(
                    "No active chat partner. Use /chat <name|number> first."
                )
            return False

        if not clean_path or not os.path.isfile(clean_path):
            if self.on_error:
                self.on_error(f"File not found: {clean_path or filepath}")
            return False

        t = threading.Thread(
            target=self._send_file_worker,
            args=(partner, sock, send_lock, clean_path),
            name=f"file-send-{partner}",
            daemon=True,
        )
        with self._lock:
            self._file_threads = [ft for ft in self._file_threads if ft.is_alive()]
            self._file_threads.append(t)
        t.start()
        return True

    def _send_file_worker(
        self,
        partner: str,
        sock: socket.socket,
        send_lock: threading.Lock,
        filepath: str,
    ) -> None:
        """Stream a file in CHUNK_SIZE blocks over the peer socket."""
        filename = os.path.basename(filepath)
        try:
            total_size = os.path.getsize(filepath)
            header = encode_file_header(filename, total_size)
        except OSError as exc:
            if self.on_error:
                self.on_error(f"Cannot read file {filename}: {exc}")
            return

        label = f"Sending {filename}"
        try:
            with open(filepath, "rb") as f:
                with send_lock:
                    sock.sendall(header)
                    sent = 0
                    if total_size == 0 and self.on_progress:
                        self.on_progress(label, 0, 0)
                    while sent < total_size:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        sock.sendall(chunk)
                        sent += len(chunk)
                        if self.on_progress:
                            self.on_progress(label, sent, total_size)
        except OSError as exc:
            if self.on_error:
                self.on_error(f"File transfer failed for {filename}: {exc}")
            self._cleanup_connection(partner, sock, notify=True)
            return

        if self.on_system:
            self.on_system(
                f"Sending {filename} ({_format_size(total_size)}) ... 100% Done."
            )

    def _accept_loop(self) -> None:
        """Accept incoming TCP peer connections."""
        while not self._stop_event.is_set():
            server = self._server_sock
            if server is None:
                break
            try:
                conn, addr = server.accept()
                conn.settimeout(None)
                t = threading.Thread(
                    target=self._receiver_loop,
                    args=(conn, addr, None),
                    name=f"tcp-recv-{addr[0]}:{addr[1]}",
                    daemon=True,
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                if self._stop_event.is_set():
                    break

    def _receiver_loop(
        self,
        sock: socket.socket,
        addr: tuple[str, int],
        initial_peer_name: str | None,
    ) -> None:
        """Read framed TCP messages and files from a connected peer."""
        peer_name = initial_peer_name or f"{addr[0]}:{addr[1]}"
        registered = initial_peer_name is not None

        try:
            while not self._stop_event.is_set():
                header = read_frame_header(sock)
                if header is None:
                    break

                frame_type = header[0]
                if frame_type == "PEER":
                    _, remote_name, _ = header
                    peer_name = remote_name
                    with self._lock:
                        self._connections[peer_name] = sock
                        self._send_locks.setdefault(peer_name, threading.Lock())
                    registered = True
                    continue

                if not registered:
                    with self._lock:
                        self._connections[peer_name] = sock
                        self._send_locks.setdefault(peer_name, threading.Lock())
                    registered = True

                if frame_type == "BYE":
                    break

                if frame_type == "MSG":
                    _, length = header
                    payload = recv_exact(sock, length)
                    text = payload.decode("utf-8", errors="replace")
                    self._handle_incoming_message(peer_name, text)

                elif frame_type == "FILE":
                    _, filename, size = header
                    self._receive_file(sock, peer_name, filename, size)

        except (ConnectionError, OSError, ValueError):
            pass
        finally:
            self._cleanup_connection(
                peer_name, sock, notify=not self._stop_event.is_set() and registered
            )

    def _handle_incoming_message(self, sender: str, text: str) -> None:
        """Route an incoming chat message to active display or unread queue."""
        is_active = False
        unread_count = 0
        with self._lock:
            self._chat_histories.setdefault(sender, []).append((sender, text))
            if self._current_partner == sender:
                is_active = True
            else:
                queue = self._unread_messages.setdefault(sender, [])
                queue.append((sender, text))
                unread_count = len(queue)

        if is_active:
            if self.on_chat:
                self.on_chat(sender, text)
        else:
            if self.on_unread:
                self.on_unread(sender, unread_count)

    def _receive_file(
        self, sock: socket.socket, sender: str, filename: str, total_size: int
    ) -> None:
        """Receive a file stream in chunks and save to downloads/; delete partial file on failure."""
        safe_name = os.path.basename(filename) or "received_file"
        os.makedirs(self.downloads_dir, exist_ok=True)
        dest_path = os.path.join(self.downloads_dir, safe_name)
        label = f"Receiving {safe_name} from {sender}"

        received = 0
        try:
            with open(dest_path, "wb") as f:
                if total_size == 0 and self.on_progress:
                    self.on_progress(label, 0, 0)
                while received < total_size:
                    to_read = min(CHUNK_SIZE, total_size - received)
                    chunk = sock.recv(to_read)
                    if not chunk:
                        raise ConnectionError(
                            f"Transfer interrupted at {received}/{total_size} bytes."
                        )
                    f.write(chunk)
                    received += len(chunk)
                    if self.on_progress:
                        self.on_progress(label, received, total_size)
        except Exception as exc:
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
            if self.on_error:
                self.on_error(
                    f"File transfer '{safe_name}' from {sender} failed ({exc}); partial file deleted."
                )
            raise

        if self.on_system:
            self.on_system(
                f"Received file '{safe_name}' ({_format_size(total_size)}) from {sender} -> saved to {dest_path}"
            )

    def _cleanup_connection(
        self, peer_name: str, sock: socket.socket, notify: bool
    ) -> None:
        """Remove a closed socket and notify if the active chat partner disconnected."""
        was_partner = False
        removed = False
        with self._lock:
            if self._connections.get(peer_name) is sock:
                self._connections.pop(peer_name, None)
                removed = True
                if self._current_partner == peer_name:
                    self._current_partner = None
                    was_partner = True

        try:
            sock.close()
        except OSError:
            pass

        if notify and removed and self.on_system:
            if was_partner:
                self.on_system(
                    f"{peer_name} closed the connection. Returned to main prompt."
                )
            else:
                self.on_system(f"Connection with {peer_name} closed.")
