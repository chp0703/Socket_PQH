"""Lightweight HTTP bridge serving the Zalo Web UI (fe/) connected to UDPDiscovery and TCPManager."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys
import tempfile
import threading
import time

FE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(FE_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from protocol import (  # noqa: E402
    DEFAULT_BCAST,
    DEFAULT_TCP_PORT,
    DOWNLOADS_DIR,
    UDP_PORT,
    VALID_STATUSES,
    PeerInfo,
)
from tcp_manager import TCPManager  # noqa: E402
from udp_discovery import UDPDiscovery  # noqa: E402


class BridgeState:
    """Thread-safe state connecting UDPDiscovery and TCPManager to the Zalo Web UI."""

    def __init__(self, name: str, tcp_port: int, udp_port: int, bcast_ip: str) -> None:
        self.name = name
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.downloads_dir = os.path.join(APP_DIR, DOWNLOADS_DIR)

        self._lock = threading.Lock()
        self.histories: dict[str, list[dict[str, object]]] = {}
        self.unreads: dict[str, int] = {}
        self.transfer: dict[str, object] = {"active": False, "label": "", "pct": 0}

        self.tcp = TCPManager(
            name=name,
            listen_port=tcp_port,
            downloads_dir=self.downloads_dir,
            on_chat=self._on_chat,
            on_unread=self._on_unread,
            on_system=self._on_system,
            on_error=self._on_error,
            on_progress=self._on_progress,
        )
        self.discovery = UDPDiscovery(
            name=name,
            tcp_port=tcp_port,
            udp_port=udp_port,
            bcast_ip=bcast_ip,
            on_system=self._on_system,
        )

    def start(self) -> None:
        self.tcp.start()
        self.discovery.start()

    def stop(self) -> None:
        self.discovery.stop()
        self.tcp.stop()

    def _now_str(self) -> str:
        return time.strftime("%H:%M")

    def _on_chat(self, sender: str, text: str) -> None:
        partner = self.tcp.get_current_partner() or sender
        key = partner if sender == self.name else sender
        with self._lock:
            self.histories.setdefault(key, []).append(
                {"sender": sender, "text": text, "time": self._now_str()}
            )

    def _on_unread(self, sender: str, count: int) -> None:
        with self._lock:
            self.unreads[sender] = count
            # Pull latest message from TCPManager's internal history for UI preview
            raw_hist = self.tcp._chat_histories.get(sender, [])
            if raw_hist:
                last_sender, last_text = raw_hist[-1]
                self.histories.setdefault(sender, []).append(
                    {"sender": last_sender, "text": last_text, "time": self._now_str()}
                )

    def _on_system(self, message: str) -> None:
        print(f"[*] {message}")
        if message.startswith("Received file '"):
            try:
                parts = message.split("'")
                fname = parts[1]
                from_part = message.split(" from ")[1].split(" -> ")[0]
                with self._lock:
                    self.histories.setdefault(from_part, []).append(
                        {
                            "sender": from_part,
                            "text": f"[File] {fname}",
                            "file": {"name": fname, "size": "Đã lưu vào downloads/"},
                            "time": self._now_str(),
                        }
                    )
            except Exception:
                pass

    def _on_error(self, message: str) -> None:
        print(f"[!] {message}", file=sys.stderr)

    def _on_progress(self, label: str, current: int, total: int) -> None:
        pct = int((current * 100) / total) if total > 0 else 100
        with self._lock:
            self.transfer = {
                "active": current < total,
                "label": label,
                "pct": pct,
            }

    def snapshot(self) -> dict[str, object]:
        peers = [
            {
                "name": p.name,
                "ip": p.ip,
                "tcp_port": p.tcp_port,
                "status": p.status,
            }
            for p in self.discovery.get_peers()
        ]
        with self._lock:
            return {
                "selfName": self.name,
                "tcpPort": self.tcp_port,
                "udpPort": self.udp_port,
                "peers": peers,
                "histories": self.histories,
                "unreads": self.unreads,
                "transfer": self.transfer,
            }


def make_handler(state: BridgeState):
    """Create a request handler class bound to BridgeState."""

    class ZaloUIHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=FE_DIR, **kwargs)

        def log_message(self, format: str, *args) -> None:
            return

        def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            if self.path.startswith("/api/state"):
                self._send_json(state.snapshot())
                return
            super().do_GET()

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            content_type = self.headers.get("Content-Type", "")

            if self.path == "/api/chat":
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                target = str(body.get("target", "")).strip()
                peer = state.discovery.resolve_peer(target) or PeerInfo(
                    name=target, ip="127.0.0.1", tcp_port=0
                )
                state.tcp.switch_chat(peer)
                with state._lock:
                    state.unreads.pop(target, None)
                self._send_json({"ok": True})
                return

            if self.path == "/api/send":
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                target = str(body.get("target", "")).strip()
                text = str(body.get("text", "")).strip()
                if target:
                    peer = state.discovery.resolve_peer(target)
                    if peer:
                        state.tcp.switch_chat(peer)
                ok = state.tcp.send_chat(text) if text else False
                self._send_json({"ok": ok})
                return

            if self.path == "/api/status":
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                status = str(body.get("status", "online")).lower()
                if status in VALID_STATUSES:
                    state.discovery.set_status(status)
                self._send_json({"ok": True})
                return

            if self.path == "/api/send_file" and "multipart/form-data" in content_type:
                raw_data = self.rfile.read(length)
                boundary = content_type.split("boundary=")[-1].encode("utf-8")
                parts = raw_data.split(b"--" + boundary)
                target = ""
                file_name = "upload.bin"
                file_bytes = b""
                for part in parts:
                    if b"Content-Disposition" not in part:
                        continue
                    header_end = part.find(b"\r\n\r\n")
                    if header_end == -1:
                        continue
                    headers_raw = part[:header_end].decode("utf-8", errors="replace")
                    content = part[header_end + 4 :]
                    if content.endswith(b"\r\n"):
                        content = content[:-2]
                    if 'name="target"' in headers_raw:
                        target = content.decode("utf-8", errors="replace").strip()
                    elif 'name="file"' in headers_raw:
                        if 'filename="' in headers_raw:
                            file_name = headers_raw.split('filename="')[1].split('"')[0]
                        file_bytes = content

                if target:
                    peer = state.discovery.resolve_peer(target)
                    if peer:
                        state.tcp.switch_chat(peer)

                tmp_dir = tempfile.mkdtemp(prefix="zalo_fe_upload_")
                tmp_path = os.path.join(tmp_dir, os.path.basename(file_name))
                with open(tmp_path, "wb") as f:
                    f.write(file_bytes)
                ok = state.tcp.send_file_async(tmp_path)
                if ok:
                    with state._lock:
                        state.histories.setdefault(target, []).append(
                            {
                                "sender": state.name,
                                "text": f"[File] {file_name}",
                                "file": {
                                    "name": file_name,
                                    "size": f"{len(file_bytes) / 1024:.1f} KB",
                                },
                                "time": state._now_str(),
                            }
                        )
                self._send_json({"ok": ok})
                return

            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    return ZaloUIHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Zalo Web UI Bridge for LAN Chat P2P")
    parser.add_argument("--name", default="Châu Hòa Phát", help="Display name")
    parser.add_argument("--port", type=int, default=DEFAULT_TCP_PORT, help="TCP port")
    parser.add_argument("--udp-port", type=int, default=UDP_PORT, help="UDP port")
    parser.add_argument("--bcast", default=DEFAULT_BCAST, help="UDP broadcast IP")
    parser.add_argument("--web-port", type=int, default=8080, help="Local Web UI port")
    args = parser.parse_args()

    state = BridgeState(args.name, args.port, args.udp_port, args.bcast)
    state.start()

    server = ThreadingHTTPServer(("127.0.0.1", args.web_port), make_handler(state))
    print(f"[*] Zalo Web UI running at: http://127.0.0.1:{args.web_port}")
    print(f"[*] P2P Node '{args.name}' — TCP port {args.port} | UDP port {args.udp_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down Zalo Web UI...")
    finally:
        server.server_close()
        state.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
