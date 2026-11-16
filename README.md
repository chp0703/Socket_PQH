# Socket_PQH — LAN Chat & File Sharing (P2P)

Đồ án môn học **Lập trình Mạng (Socket Programming)**: xây dựng ứng dụng **chat và chia sẻ file ngang hàng (Peer-to-Peer)** chạy trên giao diện dòng lệnh (Command-Line) trong mạng LAN/Wi-Fi, sử dụng trực tiếp Socket API chuẩn của Python với cả hai giao thức **UDP** và **TCP**.

---

## Thông tin đồ án

- **Tên đồ án:** LAN Chat & File Sharing (P2P)
- **Ngôn ngữ & Nền tảng:** Python 3 (thư viện chuẩn `socket`, `threading`)
- **Thư viện hỗ trợ CLI:** `prompt_toolkit>=3.0.43`, `rich>=13.7.0`, `tqdm>=4.66.0`
- **Mô hình mạng:** Peer-to-Peer (mọi node đều chạy cùng một chương trình, không cần server trung tâm)
  - **UDP (`9999`):** Phát hiện peer tự động (Peer Discovery) và cập nhật trạng thái (`online` / `away`).
  - **TCP (`5000+`):** Truyền tin nhắn chat đa phiên và truyền file tin cậy kèm thanh tiến độ.

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
└── lan-chat-p2p/                 # Thư mục mã nguồn và tài liệu kỹ thuật chính
    ├── downloads/
    │   └── .gitkeep              # Giữ thư mục lưu file nhận về trong Git
    ├── lanchat.py                # Điểm khởi chạy (entry point), CLI parser & luồng điều phối chính
    ├── protocol.py               # Định dạng bản tin UDP, TCP message framing & recv_exact
    ├── udp_discovery.py          # UDP broadcaster/listener, quản lý danh sách peer & timeout 10s
    ├── tcp_manager.py            # TCP acceptor/receiver đa peer, unread counter & file transfer
    ├── console_ui.py             # Giao diện console (prompt_toolkit, rich, tqdm) không đứt dòng gõ
    ├── requirements.txt          # Danh sách thư viện Python bên thứ ba
    ├── README.md                 # Hướng dẫn cài đặt, chạy, kiểm thử và đặc tả kỹ thuật chi tiết
    └── .gitignore                # Quy tắc loại trừ file tạm, venv và file trong downloads/
```

---

## Tài liệu Kỹ thuật & Hướng dẫn Chạy

Toàn bộ hướng dẫn cài đặt môi trường, cách khởi chạy (trên nhiều máy LAN hoặc nhiều instance trên một máy), danh sách lệnh CLI, kiến trúc đa luồng, giao thức đóng khung bản tin, xử lý lỗi và kiểm thử Wireshark được trình bày đầy đủ tại:

👉 **[lan-chat-p2p/README.md](./lan-chat-p2p/README.md)**

### Khởi chạy nhanh

```bash
cd lan-chat-p2p
pip install -r requirements.txt
python lanchat.py --name <TenCuaBan>
```

> **Lưu ý trạng thái hiện tại:** Repository đã được khởi tạo đầy đủ cấu trúc cây thư mục, file cấu hình (`requirements.txt`, `.gitignore`) và bộ tài liệu đặc tả kỹ thuật; các file mã nguồn `.py` hiện đang ở dạng khung file trống sẵn sàng cho giai đoạn hiện thực từng milestone.
