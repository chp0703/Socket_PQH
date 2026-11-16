# LAN Chat & File Sharing (P2P)

Ứng dụng chat và chia sẻ file P2P trên dòng lệnh bằng Python (`socket`, `threading`), sử dụng **UDP (`9999`)** để tìm peer/trạng thái và **TCP (`5000+`)** để chat và truyền file.

> **Trạng thái:** Đã hoàn thiện cấu trúc thư mục và file cấu hình; các file `.py` đang ở dạng khung trống để triển khai mã nguồn.

---

## 1. Cài đặt (Install)

**Yêu cầu:** Python 3.8+

```bash
cd lan-chat-p2p

# (Khuyên dùng) Tạo và kích hoạt môi trường ảo
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux / macOS:      source .venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt
```

> **Lưu ý Windows:** Khi chạy lần đầu, chọn **Allow access** trong Windows Defender Firewall cho Python để nhận được gói UDP broadcast.

---

## 2. Cách chạy (Run)

**Trên nhiều máy cùng mạng LAN/Wi-Fi:**
```bash
# Máy 1
python lanchat.py --name Quan

# Máy 2
python lanchat.py --name Minh
```

**Nhiều instance trên cùng 1 máy (test local):**
```bash
# Terminal 1
python lanchat.py --name Quan --port 5000

# Terminal 2
python lanchat.py --name Minh --port 5001
```
*(Nếu máy **offline** không có mạng, thêm `--bcast 127.255.255.255` vào cả hai lệnh.)*

---

## 3. Các lệnh sử dụng (CLI Commands)

| Lệnh | Chức năng |
| :--- | :--- |
| `/list` | Xem danh sách peer đang online (STT, tên, IP, trạng thái) |
| `/chat <name\|number>` | Mở/chuyển phiên chat TCP với peer đã chọn |
| `<nội dung>` | Gửi tin nhắn tới đối tác đang chat hiện tại |
| `/send <file>` | Gửi file tới đối tác hiện tại (hiển thị `%`, không chặn chat) |
| `/leave` | Đóng phiên chat hiện tại |
| `/status <online\|away>` | Đổi trạng thái bản thân (cập nhật qua UDP) |
| `/help` | Xem danh sách lệnh |
| `/quit` | Thoát chương trình |

- File nhận được tự động lưu vào thư mục `downloads/`.

---

## 4. Tóm tắt Kỹ thuật

- **Cấu trúc module:**
  - `lanchat.py`: Entry point, đọc CLI args & xử lý input ở Main thread.
  - `protocol.py`: Định dạng bản tin UDP, TCP framing và hàm đọc đủ byte (`recv_exact`).
  - `udp_discovery.py`: Broadcast UDP `3s/lần` (`HELLO|<name>|<tcp_port>|<status>`), cấu hình `SO_REUSEADDR`/`SO_REUSEPORT`/`SO_BROADCAST`, xóa peer nếu quá `10s` không phản hồi.
  - `tcp_manager.py`: Chấp nhận kết nối đa peer, tạo 1 receiver thread/peer, bộ đếm tin chưa đọc (`unread`), luồng gửi file riêng và xóa partial file nếu truyền lỗi.
  - `console_ui.py`: Dùng `prompt_toolkit` (`patch_stdout`) để giữ nguyên dòng đang gõ khi có tin nhắn đến, `rich` để hiển thị bảng/màu và `tqdm` cho thanh tiến độ file; đồng bộ dữ liệu dùng chung bằng `threading.Lock`.
- **TCP Message Framing:**
  - Chat: `MSG|<length>|<utf-8 text>`
  - File: `FILE|<filename>|<size_in_bytes>|<raw file bytes>`
  - Đóng kết nối: `BYE|`

---

## 5. Kiểm thử nhanh (Test)

1. Mở 2–3 terminal trên cùng máy (khác `--port`) hoặc trên 2 máy cùng LAN/Wi-Fi.
2. Kiểm tra `/list` thấy đủ peer, thử `/status away`, chat hai chiều với `/chat`, kiểm tra thông báo `unread` khi peer thứ 3 nhắn tới và gửi file bằng `/send`.
3. Kiểm tra gói tin bằng **Wireshark**:
   - UDP Discovery Broadcast: `udp.port == 9999`
   - TCP 3-way handshake & dữ liệu chat/file: `tcp.port == 5000` (hoặc port đã chọn)
