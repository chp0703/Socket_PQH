# GUIDE.md — Hướng dẫn Triển khai & Phân công Công việc

Tài liệu phân chia module, quy trình phối hợp và checklist kiểm thử cho **Phát** và **Hiển**.

---

## 1. Bảng phân công công việc

| Thành viên | File phụ trách | Nhiệm vụ chính | Nhánh Git gợi ý |
| :--- | :--- | :--- | :--- |
| **Phát** | `lan-chat-p2p/protocol.py`<br>`lan-chat-p2p/udp_discovery.py`<br>`lan-chat-p2p/lanchat.py` | - Hiện thực `PeerInfo`, encode/decode UDP `HELLO\|`, TCP framing (`MSG\|`, `FILE\|`, `BYE\|`), `recv_exact`, `read_frame_header`<br>- Hiện thực UDP discovery (`9999`), broadcast `3s`, listener, bảng peer online (`Lock`), timeout `10s`, `/status`<br>- Hiện thực CLI `argparse` (`--name`, `--port`, `--bcast`), điều phối 8 lệnh và ghép nối các module | `feat/protocol`<br>`feat/udp-discovery`<br>`feat/lanchat-cli` |
| **Hiển** | `lan-chat-p2p/console_ui.py`<br>`lan-chat-p2p/tcp_manager.py` | - Hiện thực giao diện console không vỡ dòng đang gõ (`prompt_toolkit` + `patch_stdout`), bảng `/list` (`rich`), progress bar (`tqdm`)<br>- Hiện thực TCP acceptor & kết nối tới peer, 1 receiver thread/peer, lịch sử chat & `unread` counter (`Lock`)<br>- Hiện thực truyền/nhận file theo chunk chạy thread riêng, lưu vào `downloads/`, xóa partial file khi lỗi | `feat/console-ui`<br>`feat/tcp-manager` |

> **Nguyên tắc chống xung đột:** Mỗi thành viên chỉ chỉnh sửa các file thuộc phần mình. Nếu cần đổi chữ ký hàm/class dùng chung, phải cập nhật `lan-chat-p2p/CONTRACTS.md` và thống nhất trước khi merge vào `main`.

---

## 2. Thứ tự triển khai theo Chặng

| Chặng | Phát | Hiển | Mục tiêu hoàn thành |
| :-: | :--- | :--- | :--- |
| **1** | Code `protocol.py` + test unit encode/decode/framing | Code `console_ui.py` + test nhập song song khi in từ thread nền | Có nền tảng giao thức và UI độc lập |
| **2** | Code `udp_discovery.py` + test 2 terminal (`--bcast 127.255.255.255`) | Code `tcp_manager.py` + test chat/file giữa 2 socket dựa trên `CONTRACTS.md` | Hoàn thiện tầng UDP và tầng TCP riêng biệt |
| **3** | Ghép toàn bộ trong `lanchat.py` | Phối hợp test đa peer, gửi file khi đang chat, xử lý lỗi & Wireshark | Chạy demo hoàn chỉnh trên 2+ máy LAN |

---

## 3. Prompt mẫu khi dùng AI Coding

Copy mẫu dưới đây để AI không code lan man sang file của người khác:

```text
Đọc AGENTS.md và lan-chat-p2p/CONTRACTS.md.
Chỉ hiện thực file lan-chat-p2p/<tên_file>.py theo đúng contract và ràng buộc kỹ thuật.
Không sửa các file khác, không thêm thư viện ngoài requirements.txt.
```

---

## 4. Checklist Kiểm thử trước khi Merge vào `main`

- [x] `python -m py_compile lan-chat-p2p/*.py` chạy không lỗi.
- [x] Chạy 2–3 instance cùng lúc (`--port 5000`, `5001`, `5002`) thấy nhau trong `/list` sau ~3s; tắt 1 instance biến mất sau 10s.
- [x] Đang gõ dở câu lệnh/tin nhắn mà peer khác gửi tới: chữ đang gõ được giữ nguyên phía dưới.
- [x] Peer thứ 3 nhắn khi đang chat với peer thứ 2: hiện thông báo `(N unread)`, `/chat` sang thì in đủ tin chưa đọc.
- [x] `/send <file>` chạy ở luồng riêng, hiện `%`, chat vẫn hoạt động bình thường; file nhận nằm đúng trong `downloads/` (không commit file test vào Git).
- [x] Rút kết nối hoặc gửi sai lệnh không làm crash chương trình; truyền file đứt giữa chừng phải xóa partial file.
