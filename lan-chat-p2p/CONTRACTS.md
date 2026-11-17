# CONTRACTS.md — Giao diện chuẩn giữa các Module

> Mọi module phải giữ đúng tên class, tên hàm, kiểu dữ liệu và tham số dưới đây để **Phát** và **Hiển** code song song và ghép nối vào `lanchat.py` không xung đột.

---

## 1. `protocol.py` — Hằng số, Kiểu dữ liệu & Framing

```python
UDP_PORT = 9999
DEFAULT_TCP_PORT = 5000
DEFAULT_BCAST = "255.255.255.255"
BROADCAST_INTERVAL = 3.0
PEER_TIMEOUT = 10.0
CHUNK_SIZE = 8192
DOWNLOADS_DIR = "downloads"
VALID_STATUSES = ("online", "away")

@dataclass
class PeerInfo:
    name: str
    ip: str
    tcp_port: int
    status: str = "online"
    last_seen: float = 0.0
```

**Hàm bắt buộc:**
- `encode_hello(name: str, tcp_port: int, status: str) -> bytes` → `b"HELLO|<name>|<tcp_port>|<status>"`
- `decode_hello(data: bytes) -> tuple[str, int, str] | None`
- `encode_peer(name: str, tcp_port: int) -> bytes` → `b"PEER|<name>|<tcp_port>|"` *(khung định danh kết thúc bằng `|`, gửi ngay khi mở TCP để phân biệt peer khi test nhiều instance trên 1 máy)*
- `encode_msg(text: str) -> bytes` → `b"MSG|<byte_len>|" + text.encode("utf-8")`
- `encode_file_header(filename: str, size: int) -> bytes` → `b"FILE|<basename>|<size>|"`
- `encode_bye() -> bytes` → `b"BYE|"`
- `recv_exact(sock: socket.socket, n: int) -> bytes` *(nâng `ConnectionError` nếu EOF trước khi đủ `n` byte)*
- `read_frame_header(sock: socket.socket) -> tuple | None`
  - Trả về `None` khi đóng kết nối sạch (`b""` ngay đầu frame)
  - `("PEER", name: str, tcp_port: int)`
  - `("MSG", length: int)`
  - `("FILE", filename: str, size: int)`
  - `("BYE",)`

---

## 2. `udp_discovery.py` — Peer Discovery

```python
class UDPDiscovery:
    def __init__(
        self,
        name: str,
        tcp_port: int,
        udp_port: int = UDP_PORT,
        bcast_ip: str = DEFAULT_BCAST,
        on_system: Callable[[str], None] | None = None,
    ) -> None: ...

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def set_status(self, status: str) -> None: ...
    def get_peers(self) -> list[PeerInfo]: ...
    def resolve_peer(self, target: str) -> PeerInfo | None: ...  # theo tên hoặc STT (1-based)
```

---

## 3. `tcp_manager.py` — Chat, Unread & File Transfer

```python
class TCPManager:
    def __init__(
        self,
        name: str,
        listen_port: int,
        downloads_dir: str = DOWNLOADS_DIR,
        on_chat: Callable[[str, str], None] | None = None,         # (sender, text)
        on_unread: Callable[[str, int], None] | None = None,       # (sender, count)
        on_system: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_progress: Callable[[str, int, int], None] | None = None,  # (label, sent_bytes, total_bytes)
    ) -> None: ...

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def connect_peer(self, peer: PeerInfo) -> bool: ...
    def switch_chat(self, peer: PeerInfo) -> list[tuple[str, str]]: ...  # trả về tin unread & reset đếm
    def leave_chat(self) -> None: ...
    def send_chat(self, text: str) -> bool: ...
    def send_file_async(self, filepath: str) -> bool: ...
    def get_current_partner(self) -> str | None: ...
```

---

## 4. `console_ui.py` — Giao diện Console (`prompt_toolkit`, `rich`, `tqdm`)

```python
class ConsoleUI:
    def __init__(self, prompt_text: str = "> ") -> None: ...
    def read_line(self) -> str: ...
    def print_system(self, message: str) -> None: ...
    def print_chat(self, sender: str, message: str) -> None: ...
    def print_error(self, message: str) -> None: ...
    def show_peers(self, peers: list[PeerInfo]) -> None: ...
    def show_help(self) -> None: ...
    def update_progress(self, label: str, current: int, total: int) -> None: ...
```

---

## 5. `lanchat.py` — CLI Entry Point

- Tham số dòng lệnh: `--name` *(bắt buộc)*, `--port` *(int, mặc định `5000`)*, `--bcast` *(str, mặc định `"255.255.255.255"`)*.
- Lệnh hỗ trợ: `/list`, `/chat <name|number>`, `<text>`, `/send <file>`, `/leave`, `/status <online|away>`, `/help`, `/quit`.
