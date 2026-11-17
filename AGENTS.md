# AGENTS.md — Quy tắc & Ràng buộc Codebase

Tài liệu này áp dụng cho mọi AI coding agent và thành viên khi chỉnh sửa mã nguồn trong repository `Socket_PQH`.

---

## 1. Phạm vi & Ràng buộc Công nghệ

- **Thư mục mã nguồn:** Chỉ code trong `lan-chat-p2p/`. Không tự ý tạo thêm file `.py` mới hoặc gộp các module lại thành 1 file.
- **Mạng & Đa luồng:** **Chỉ** sử dụng thư viện chuẩn Python (`socket`, `threading`, `argparse`, `os`, `time`, `dataclasses`, `pathlib`).
- **UI & Tiện ích:** **Chỉ** sử dụng 3 thư viện trong `lan-chat-p2p/requirements.txt` (`prompt_toolkit`, `rich`, `tqdm`).
- **Cấm:** Không dùng `asyncio`, framework mạng cấp cao (`aiohttp`, `twisted`, `websockets`, ...), hoặc tự thêm package ngoài.

---

## 2. Ranh giới 5 Module (Separation of Concerns)

Mọi chữ ký hàm/class dùng chung phải tuân thủ **[lan-chat-p2p/CONTRACTS.md](./lan-chat-p2p/CONTRACTS.md)**. Không code chéo trách nhiệm:

| Module | Được phép làm | Tuyệt đối KHÔNG làm |
| :--- | :--- | :--- |
| `protocol.py` | Định nghĩa hằng số, `PeerInfo`, encode/decode UDP, TCP framing, `recv_exact`, `read_frame_header` | Không tạo socket server/thread, không giữ state peer, không gọi UI/print |
| `udp_discovery.py` | UDP socket (`9999`), broadcaster `3s`, listener, bảng peer online (`Lock`), timeout `10s` | Không mở kết nối TCP, không xử lý chat/file |
| `tcp_manager.py` | TCP acceptor & client, receiver thread/peer, lịch sử chat, `unread`, gửi/nhận file (`downloads/`) | Không tự `print()` ra terminal (phải dùng UI callback) |
| `console_ui.py` | `prompt_toolkit` (`patch_stdout`), bảng `rich`, thanh tiến độ `tqdm`, lock xuất màn hình | Không chứa logic `socket` hay xử lý giao thức |
| `lanchat.py` | `argparse` (`--name`, `--port`, `--bcast`), nối các module, vòng lặp lệnh CLI & thoát sạch | Không tự parse byte stream hoặc thao tác socket cấp thấp |

---

## 3. Bất biến Kỹ thuật (Bắt buộc tuân thủ)

1. **UDP Discovery (`udp_discovery.py`):**
   - Đặt `SO_REUSEADDR = 1`, `SO_REUSEPORT = 1` (nếu hệ điều hành hỗ trợ, bọc `try/except OSError`), `SO_BROADCAST = 1` **trước khi** gọi `bind(("", 9999))`.
   - Phải tự lọc bỏ gói `HELLO` của chính mình; timeout xóa peer khi quá `10.0` giây không nhận phản hồi.
2. **TCP Message Framing (`protocol.py` & `tcp_manager.py`):**
   - Định dạng bắt buộc: `PEER|<name>|<tcp_port>|` (gửi 1 lần khi mở kết nối để định danh trên cùng máy; fallback `ip:port` nếu peer không gửi như `nc`), `MSG|<length>|<utf-8 bytes>`, `FILE|<filename>|<size_in_bytes>|<raw bytes>`, `BYE|`.
   - Phía nhận **bắt buộc** lặp `recv()` đủ byte (`recv_exact`); truyền file phải đọc/ghi theo `CHUNK_SIZE`, không nạp toàn bộ file lớn vào RAM.
3. **Thread Safety:**
   - Bảo vệ mọi dữ liệu dùng chung (`online_users`, connections, `chat_histories`, `unread_counters`, `current_partner`) bằng `threading.Lock`.
   - Không giữ Lock trong lúc chờ `recv()` blocking hoặc thực thi UI callback kéo dài.
4. **Error Handling & An toàn:**
   - Không được crash khi peer ngắt kết nối đột ngột (`b""`, `ConnectionResetError`), peer offline, thiếu file hoặc gõ sai lệnh.
   - Luôn chuẩn hóa tên file nhận bằng `os.path.basename()` để tránh path traversal; **xóa ngay partial file** trong `downloads/` nếu truyền bị gián đoạn.

---

## 4. Quy tắc làm việc cho AI Agent

- **Đọc contract trước khi code:** Luôn đọc `lan-chat-p2p/CONTRACTS.md` và `GUIDE.md` trước khi viết code.
- **Đúng phạm vi:** Chỉ chỉnh sửa các file thuộc nhiệm vụ đang được giao; không tự ý sửa module của thành viên khác.
- **Code gọn, dễ đọc:** Hàm ngắn, có type hints và docstring súc tích, không duplicate logic.
- **Kiểm chứng sau khi sửa:** Chạy `python -m py_compile lan-chat-p2p/*.py` và kiểm thử chạy thực tế với ít nhất 2 instance (`--port 5000`, `--port 5001`).
