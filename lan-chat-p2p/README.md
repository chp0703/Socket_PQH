# LAN Chat & File Sharing (P2P) — Hướng dẫn Cài đặt & Chạy

Ứng dụng chat và chia sẻ file ngang hàng (**Peer-to-Peer**) trong mạng LAN/Wi-Fi bằng Python (`socket`, `threading`), sử dụng **UDP (`9999`)** để tự động tìm peer/cập nhật trạng thái và **TCP (`5000+`)** để chat đa phiên và truyền file.

Hỗ trợ 2 chế độ giao diện dùng chung một lõi mạng P2P:
1. **Giao diện Zalo Web UI (`fe/server.py`):** Tự động mở trên Google Chrome / trình duyệt web, chỉ hiển thị người dùng LAN thực tế, đóng/kéo thanh `Thông tin [LAN]`, thả Like `👍` khi rê chuột, gửi/nhận file lưu vào `downloads/` và bấm mở được ngay.
2. **Giao diện Dòng lệnh (`lanchat.py`):** Tích hợp `prompt_toolkit` (`patch_stdout`), bảng `rich` và thanh tiến độ `tqdm` không làm vỡ dòng đang gõ khi có tin nhắn đến.

---

## 1. Thành viên thực hiện

| STT | Họ và tên | MSSV |
| :-: | :--- | :---: |
| 1 | Châu Hòa Phát | `25127224` |
| 2 | Huỳnh Nguyễn Thế Hiển | `25127327` |
| 3 | Đỗ Nguyễn Nhật Quang | `25127478` |

---

## 2. Cài đặt (Install)

**Yêu cầu:** Python 3.8+

```bash
cd lan-chat-p2p

# Tạo và kích hoạt môi trường ảo (khuyên dùng)
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux / macOS:      source .venv/bin/activate

# Cài đặt thư viện (prompt_toolkit, rich, tqdm)
pip install -r requirements.txt
```

> **Lưu ý trên Windows:**
> - Khi chạy lần đầu, tích chọn **Private** và **Public networks** rồi bấm **Allow access** trong Windows Defender Firewall để nhận được gói UDP broadcast cổng `9999`.
> - Nếu máy cài nhiều bản Python (ví dụ MSYS2 và Python chuẩn), dùng `py -3.12` thay cho `python`.

---

## 3. Cách chạy (Run)

### 3.1. Chạy Giao diện Zalo Web UI (`fe/server.py`)

**Trên 2 máy tính khác nhau cùng mạng LAN/Wi-Fi (hoặc Hotspot):**
```bash
# Máy 1 (Phát)
python fe/server.py --name "Phat" --port 5000 --web-port 8080

# Máy 2 (Quang / Hiển)
python fe/server.py --name "Quan" --port 5000 --web-port 8080
```

**Test 2 người trên cùng 1 máy tính (mở 2 cửa sổ Terminal):**
```bash
# Terminal 1 -> tự động mở http://127.0.0.1:8080 trên Chrome
python fe/server.py --name "Phat" --port 5000 --web-port 8080

# Terminal 2 -> tự động mở http://127.0.0.1:8081 trên Chrome
python fe/server.py --name "Hien" --port 5001 --web-port 8081
```
*(Nếu máy hoàn toàn **offline** không có mạng, thêm `--bcast 127.255.255.255` vào cuối lệnh; nếu không muốn tự bật trình duyệt, thêm `--no-browser`).*

**Tính năng trên giao diện Zalo Web UI:**
- Cột trái chỉ hiển thị các peer LAN đang kết nối; bấm vào tên peer để mở khung chat TCP.
- Rê chuột vào tin nhắn để hiện nút `👍`, bấm thả mới hiện bộ đếm `👍 1`.
- Bấm icon kẹp giấy `📎` để gửi file qua TCP: file tự lưu vào `lan-chat-p2p/downloads/`, hỗ trợ xem trước ảnh và có nút **"Mở ngay"** (mở trực tiếp file trên hệ điều hành) + **"Mở thư mục"** (hiện file trong Windows Explorer).
- Thanh **`Thông tin [LAN]`** bên phải có thể kéo chuột thay đổi độ rộng hoặc đóng/mở bằng nút `❯` / `❮ Thông tin [LAN]`.

---

### 3.2. Chạy Giao diện Dòng lệnh CLI (`lanchat.py`)

**Trên nhiều máy cùng mạng LAN/Wi-Fi:**
```bash
# Máy 1
python lanchat.py --name Phat

# Máy 2
python lanchat.py --name Hien
```

**Nhiều instance trên cùng 1 máy:**
```bash
# Terminal 1
python lanchat.py --name Phat --port 5000

# Terminal 2
python lanchat.py --name Hien --port 5001
```

| Lệnh CLI | Chức năng |
| :--- | :--- |
| `/list` | Hiển thị bảng người dùng đang online (`#`, `Name`, `IP Address`, `TCP Port`, `Status`) |
| `/chat <name\|number>` | Mở hoặc chuyển phiên chat TCP với peer theo tên hoặc số thứ tự trên `/list` |
| `<nội dung bất kỳ>` | Gửi tin nhắn văn bản tới đối tác đang chat hiện tại |
| `/send <đường_dẫn_file>` | Gửi file tới đối tác hiện tại trên luồng riêng (hiển thị thanh tiến độ `%`, không chặn chat) |
| `/leave` | Đóng phiên chat hiện tại và quay về dấu nhắc chính |
| `/status <online\|away>` | Đổi trạng thái bản thân (`online` hoặc `away`), phát tức thì qua UDP |
| `/help` | Hiển thị bảng danh sách các lệnh hỗ trợ |
| `/quit` | Gửi thông báo đóng kết nối (`BYE\|`) và thoát chương trình sạch sẽ |

---

## 4. Tóm tắt Kỹ thuật

- **5 module lõi Python + cầu nối Web UI:**
  - `protocol.py`: Định nghĩa `PeerInfo`, encode/decode gói UDP `HELLO|<name>|<tcp_port>|<status>`, đóng khung TCP (`PEER|`, `MSG|`, `FILE|`, `BYE|`), `recv_exact()` và `read_frame_header()`.
  - `udp_discovery.py`: Broadcast UDP định kỳ mỗi `3s`, phản hồi tức thì khi phát hiện peer mới online, cấu hình `SO_REUSEADDR`/`SO_REUSEPORT`/`SO_BROADCAST` trước `bind(("", 9999))`, xóa peer quá `10s` không phản hồi.
  - `tcp_manager.py`: Lắng nghe kết nối TCP đa peer (`1 receiver thread / peer`), bảo vệ dữ liệu chung bằng `threading.Lock` và `_send_locks` riêng từng peer, lưu hàng đợi `unread`, truyền file theo `CHUNK_SIZE = 8192` trên thread riêng, chống path traversal bằng `os.path.basename()` và xóa partial file trong `downloads/` nếu truyền bị ngắt.
  - `console_ui.py`: Dùng `prompt_toolkit` (`patch_stdout(raw=True)`), `rich.table.Table` và `tqdm`.
  - `lanchat.py`: CLI entry point và điều phối lệnh.
  - `fe/server.py` + `fe/{index.html,styles.css,app.js}`: Dùng `ThreadingHTTPServer` chuẩn của Python kết nối trực tiếp vào `UDPDiscovery` và `TCPManager`.
- **Định dạng khung bản tin TCP (TCP Framing):**
  - Định danh khi mở kết nối: `PEER|<name>|<tcp_port>|` *(tự động fallback về `ip:port` nếu test bằng `netcat`)*
  - Tin nhắn văn bản: `MSG|<length>|<utf-8 bytes>`
  - Truyền file: `FILE|<filename>|<size_in_bytes>|<raw file bytes>`
  - Ngắt kết nối: `BYE|`

---

## 5. Kiểm tra Gói tin bằng Wireshark

- **UDP Discovery Broadcast:** `udp.port == 9999` (quan sát gói `HELLO|<name>|<tcp_port>|<status>` gửi tới `255.255.255.255` mỗi 3 giây).
- **TCP 3-Way Handshake & Chat/File Stream:** `tcp.port == 5000` (quan sát quá trình bắt tay `SYN` → `SYN, ACK` → `ACK`, khung `PEER|`, `MSG|`, `FILE|` và `BYE|`).
