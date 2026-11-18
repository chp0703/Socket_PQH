# Socket_PQH — LAN Chat & File Sharing (P2P)

Đồ án môn học **Lập trình Mạng (Socket Programming)**: ứng dụng **chat và chia sẻ file ngang hàng (Peer-to-Peer)** chạy trên giao diện dòng lệnh (Command-Line) trong mạng LAN/Wi-Fi, sử dụng trực tiếp Socket API chuẩn của Python với cả hai giao thức **UDP** và **TCP**.

---

## Thông tin đồ án

- **Tên đồ án:** LAN Chat & File Sharing (P2P)
- **Ngôn ngữ & Nền tảng:** Python 3 (thư viện chuẩn `socket`, `threading`, `argparse`, `dataclasses`)
- **Thư viện hỗ trợ CLI:** `prompt_toolkit>=3.0.43`, `rich>=13.7.0`, `tqdm>=4.66.0`
- **Mô hình mạng:** Peer-to-Peer (mọi node đều chạy cùng một chương trình `lanchat.py`, không cần server trung tâm)
  - **UDP (`9999`):** Phát hiện peer tự động (Peer Discovery, broadcast mỗi `3s`, phản hồi tức thì khi có peer mới, timeout `10s`) và cập nhật trạng thái (`online` / `away`).
  - **TCP (`5000+`):** Truyền tin nhắn chat đa phiên (lưu hàng đợi `unread` khi đang chat với peer khác) và truyền file tin cậy theo chunk kèm thanh tiến độ `%`.

---

## Thành viên nhóm

| STT | Họ và tên |
| :-: | :--- |
| 1 | Châu Hòa Phát |
| 2 | Huỳnh Nguyễn Thế Hiển |
| 3 | Đỗ Nguyễn Nhật Quang |

---

## Cấu trúc Repository

```text
Socket_PQH/
├── README.md                     # Thông tin tổng quan đồ án, thành viên và cấu trúc repo
├── AGENTS.md                     # Quy tắc kiến trúc và ràng buộc kỹ thuật cho codebase
├── GUIDE.md                      # Phân công công việc, lộ trình triển khai và checklist kiểm thử
└── lan-chat-p2p/                 # Thư mục mã nguồn ứng dụng chính
    ├── downloads/
    │   └── .gitkeep              # Thư mục lưu file nhận về qua TCP
    ├── lanchat.py                # Điểm khởi chạy (entry point), CLI parser & vòng lặp điều phối lệnh
    ├── protocol.py               # Hằng số giao thức, PeerInfo, encode/decode UDP & TCP framing
    ├── udp_discovery.py          # UDP broadcaster/listener, quản lý danh sách peer & timeout 10s
    ├── tcp_manager.py            # TCP acceptor/receiver đa peer, unread counter & file transfer
    ├── console_ui.py             # Giao diện console (prompt_toolkit, rich, tqdm) không đứt dòng gõ
    ├── CONTRACTS.md              # Hợp đồng giao diện (API contracts) giữa 5 module Python
    ├── requirements.txt          # Danh sách thư viện Python bên thứ ba
    ├── README.md                 # Hướng dẫn cài đặt, chạy, lệnh CLI và tóm tắt kỹ thuật
    └── .gitignore                # Quy tắc loại trừ file tạm, venv và file nhận trong downloads/
```

---

## Hướng dẫn Chạy Nhanh

Xem hướng dẫn chi tiết tại **[lan-chat-p2p/README.md](./lan-chat-p2p/README.md)**.

```bash
cd lan-chat-p2p
pip install -r requirements.txt

# Chạy trên mạng LAN/Wi-Fi (mặc định TCP port 5000, UDP port 9999)
python lanchat.py --name Quan

# Hoặc chạy nhiều instance trên cùng 1 máy
python lanchat.py --name Quan --port 5000
python lanchat.py --name Minh --port 5001
```
