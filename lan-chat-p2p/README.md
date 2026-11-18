# LAN Chat & File Sharing (P2P)

Ứng dụng chat và chia sẻ file P2P trên dòng lệnh bằng Python (`socket`, `threading`), sử dụng **UDP (`9999`)** để tự động tìm peer/cập nhật trạng thái và **TCP (`5000+`)** để chat đa phiên và truyền file.

---

## 1. Cài đặt (Install)

**Yêu cầu:** Python 3.8+

```bash
cd lan-chat-p2p

# Tạo và kích hoạt môi trường ảo (khuyên dùng)
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux / macOS:      source .venv/bin/activate

# Cài đặt thư viện giao diện CLI (prompt_toolkit, rich, tqdm)
pip install -r requirements.txt
```

> **Lưu ý trên Windows:**
> - Khi chạy lần đầu, bấm **Allow access** trong Windows Defender Firewall để Python nhận được gói UDP broadcast.
> - Nếu máy cài nhiều bản Python (ví dụ MSYS2 và Python chuẩn), dùng `py -3.12 -m venv .venv` để tạo môi trường ảo đúng bản Python chuẩn.

---

## 2. Cách chạy (Run)

**Tham số dòng lệnh hỗ trợ (`python lanchat.py -h`):**
- `--name <tên>`: Tên hiển thị của bạn trên mạng LAN *(bắt buộc)*.
- `--port <cổng>`: Cổng TCP lắng nghe *(mặc định: `5000`)*.
- `--bcast <ip>`: Địa chỉ IP broadcast UDP *(mặc định: `255.255.255.255`; dùng `127.255.255.255` nếu máy hoàn toàn offline)*.
- `--udp-port <cổng>`: Cổng UDP discovery *(mặc định: `9999`)*.

**Trường hợp 1 — Chạy trên nhiều máy cùng mạng LAN/Wi-Fi:**
```bash
# Máy 1
python lanchat.py --name Quan

# Máy 2
python lanchat.py --name Minh
```

**Trường hợp 2 — Chạy nhiều instance trên cùng 1 máy (test local):**
```bash
# Terminal 1
python lanchat.py --name Quan --port 5000

# Terminal 2
python lanchat.py --name Minh --port 5001

# Terminal 3
python lanchat.py --name Huy --port 5002
```
*(Nếu máy **offline** không kết nối Wi-Fi/LAN, thêm `--bcast 127.255.255.255` vào các lệnh trên.)*

---

## 3. Các lệnh sử dụng (CLI Commands)

| Lệnh | Chức năng |
| :--- | :--- |
| `/list` | Hiển thị bảng người dùng đang online (`#`, `Name`, `IP Address`, `TCP Port`, `Status`) |
| `/chat <name\|number>` | Mở hoặc chuyển phiên chat TCP với peer theo tên hoặc số thứ tự trên `/list` |
| `<nội dung bất kỳ>` | Gửi tin nhắn văn bản tới đối tác đang chat hiện tại |
| `/send <đường_dẫn_file>` | Gửi file tới đối tác hiện tại trên luồng riêng (hiển thị thanh tiến độ `%`, không chặn chat) |
| `/leave` | Đóng phiên chat hiện tại và quay về dấu nhắc chính |
| `/status <online\|away>` | Đổi trạng thái bản thân (`online` hoặc `away`), phát tức thì qua UDP |
| `/help` | Hiển thị bảng danh sách các lệnh hỗ trợ |
| `/quit` | Gửi thông báo đóng kết nối (`BYE\|`) và thoát chương trình sạch sẽ |

- File nhận được tự động lưu vào thư mục `lan-chat-p2p/downloads/`.

---

## 4. Tóm tắt Kỹ thuật

- **Cấu trúc 5 module:**
  - `lanchat.py`: Entry point, phân tích CLI args (`argparse`), nối callbacks và chạy vòng lặp lệnh ở Main thread.
  - `protocol.py`: Định nghĩa `PeerInfo`, encode/decode gói UDP `HELLO|`, đóng khung TCP (`PEER|`, `MSG|`, `FILE|`, `BYE|`), hàm đọc đủ byte `recv_exact()` và `read_frame_header()`.
  - `udp_discovery.py`: Broadcast UDP định kỳ mỗi `3s` (`HELLO|<name>|<tcp_port>|<status>`), phản hồi tức thì khi phát hiện peer mới, cấu hình `SO_REUSEADDR`/`SO_REUSEPORT`/`SO_BROADCAST`, tự động xóa peer sau `10s` không phản hồi.
  - `tcp_manager.py`: Lắng nghe kết nối TCP đa peer (`1 receiver thread / peer`), lưu lịch sử & đếm tin chưa đọc (`unread`) khi nhận tin từ peer không phải đối tác hiện tại, gửi file theo `CHUNK_SIZE = 8192` trên thread riêng, chuẩn hóa `os.path.basename()` và tự động xóa partial file trong `downloads/` nếu truyền bị ngắt.
  - `console_ui.py`: Dùng `prompt_toolkit` (`patch_stdout`) để giữ nguyên dòng đang gõ khi có tin nhắn đến, `rich` để kẻ bảng/tô màu và `tqdm` cho thanh tiến độ truyền file; đồng bộ xuất màn hình bằng `threading.Lock`.
- **Định dạng khung bản tin TCP (TCP Framing):**
  - Định danh khi mở kết nối: `PEER|<name>|<tcp_port>|` *(tự động fallback về `ip:port` nếu test bằng `netcat`)*
  - Tin nhắn văn bản: `MSG|<length>|<utf-8 bytes>`
  - Truyền file: `FILE|<filename>|<size_in_bytes>|<raw file bytes>`
  - Ngắt kết nối: `BYE|`

---

## 5. Kiểm thử nhanh & Wireshark

1. Mở 2–3 terminal chạy `lanchat.py` với `--port 5000`, `5001`, `5002`.
2. Gõ `/list` kiểm tra danh sách peer, `/status away` đổi trạng thái, `/chat 1` để chat hai chiều, nhắn từ terminal thứ 3 để kiểm tra thông báo `(1 unread)` rồi chuyển sang bằng `/chat`, và gửi file bằng `/send <file>`.
3. Kiểm tra gói tin bằng **Wireshark**:
   - UDP Discovery Broadcast: `udp.port == 9999`
   - TCP 3-way handshake & dữ liệu chat/file: `tcp.port == 5000` (hoặc port đã chọn)
