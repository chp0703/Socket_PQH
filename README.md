# Socket_PQH — LAN Chat & File Sharing (P2P)

Đồ án môn học **Lập trình Mạng (Socket Programming)**: ứng dụng **chat và chia sẻ file ngang hàng (Peer-to-Peer)** trong mạng LAN/Wi-Fi sử dụng trực tiếp Socket API chuẩn của Python (`socket`, `threading`) với cả hai giao thức **UDP** và **TCP**. Hỗ trợ song song **Giao diện Zalo Web UI (`fe/`)** và **Giao diện Dòng lệnh (`CLI`)**.

---

## Thông tin đồ án

- **Tên đồ án:** LAN Chat & File Sharing (P2P)
- **Ngôn ngữ & Thư viện chuẩn:** Python 3 (`socket`, `threading`, `argparse`, `dataclasses`, `http.server`)
- **Thư viện hỗ trợ CLI:** `prompt_toolkit>=3.0.43`, `rich>=13.7.0`, `tqdm>=4.66.0`
- **Mô hình mạng:** Peer-to-Peer phi tập trung (mọi máy chạy cùng chương trình, vừa là Client vừa là Server)
  - **UDP (`9999`):** Tự động khám phá peer (Peer Discovery, broadcast mỗi `3s`, phản hồi tức thì khi có peer mới, timeout `10s`) và cập nhật trạng thái (`online` / `away`).
  - **TCP (`5000+`):** Truyền tin nhắn chat đa phiên (lưu hàng đợi `unread` khi đang chat với peer khác) và truyền file tin cậy theo chunk (`8192 bytes`) kèm thanh tiến độ `%`.

---

## Thành viên nhóm

| STT | Họ và tên | MSSV |
| :-: | :--- | :---: |
| 1 | Châu Hòa Phát | `25127224` |
| 2 | Huỳnh Nguyễn Thế Hiển | `25127327` |
| 3 | Đỗ Nguyễn Nhật Quang | `25127478` |

---

## Cấu trúc Repository

```text
Socket_PQH/
├── README.md                     # Thông tin tổng quan đồ án, thành viên (MSSV) và cấu trúc repo
├── AGENTS.md                     # Quy tắc kiến trúc và ràng buộc kỹ thuật của codebase
├── GUIDE.md                      # Phân công công việc, lộ trình triển khai và checklist kiểm thử
├── REPORT.md                     # Báo cáo kỹ thuật đồ án (Markdown)
├── REPORT.pdf                    # Báo cáo kỹ thuật đồ án (định dạng tiểu luận ĐH KHTN - ĐHQG HCM)
└── lan-chat-p2p/                 # Thư mục mã nguồn ứng dụng chính
    ├── downloads/
    │   └── .gitkeep              # Thư mục lưu file gửi/nhận qua TCP
    ├── fe/                       # Giao diện Zalo PC Web UI kết nối trực tiếp lõi UDP/TCP
    │   ├── index.html            # Khung giao diện Zalo LAN P2P
    │   ├── styles.css            # Thiết kế giao diện Zalo, thanh Thông tin [LAN] kéo/đóng & hover Like
    │   ├── app.js                # Logic đồng bộ peer LAN, chat, thả Like và mở file trực tiếp
    │   └── server.py             # Cầu nối HTTP (stdlib http.server) nối Web UI với UDPDiscovery & TCPManager
    ├── tests/
    │   └── test_p2p.py           # Bộ kiểm thử tự động (protocol, UDP, TCP, CLI, xử lý lỗi, Web UI)
    ├── lanchat.py                # Entry point chế độ CLI, argparse & vòng lặp điều phối 8 lệnh
    ├── protocol.py               # Hằng số giao thức, PeerInfo, encode/decode UDP & TCP framing
    ├── udp_discovery.py          # UDP broadcaster/listener (cổng 9999), bảng peer online & timeout 10s
    ├── tcp_manager.py            # TCP acceptor/receiver đa peer, unread counter & luồng truyền file
    ├── console_ui.py             # Giao diện terminal (prompt_toolkit patch_stdout, rich, tqdm)
    ├── CONTRACTS.md              # Hợp đồng giao diện (API contracts) giữa các module Python
    ├── requirements.txt          # Danh sách thư viện Python bên thứ ba
    ├── README.md                 # Hướng dẫn cài đặt, chạy (Web UI & CLI), lệnh và tóm tắt kỹ thuật
    └── .gitignore                # Quy tắc loại trừ cache Python, venv và file nhận trong downloads/
```

---

## Hướng dẫn Chạy Nhanh

Xem hướng dẫn cài đặt và kiểm thử chi tiết tại **[lan-chat-p2p/README.md](./lan-chat-p2p/README.md)**.

```bash
cd lan-chat-p2p
pip install -r requirements.txt

# Cách 1: Chạy Giao diện Zalo Web UI (tự động mở trên Google Chrome / Trình duyệt)
python fe/server.py --name "Phat" --port 5000 --web-port 8080

# Cách 2: Chạy Giao diện Dòng lệnh (Console CLI)
python lanchat.py --name "Phat" --port 5000
```
*(Chế độ Zalo Web UI và chế độ Console CLI dùng chung giao thức UDP `9999` và TCP `5000+`, có thể tự động nhìn thấy nhau, chat và gửi file xuyên qua nhau).*
