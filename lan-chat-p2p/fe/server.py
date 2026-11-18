"""Lightweight HTTP bridge serving the Zalo Web UI (fe/) connected to UDPDiscovery and TCPManager."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

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
from tcp_manager import TCPManager, _format_size  # noqa: E402
from udp_discovery import UDPDiscovery  # noqa: E402


def open_in_chrome_or_default(url: str) -> None:
    """Open the given URL in Google Chrome on Windows if available, else default external browser."""
    if sys.platform.startswith("win"):
        candidate_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(
                r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
            ),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for path in candidate_paths:
            if os.path.isfile(path):
                try:
                    subprocess.Popen([path, url])
                    return
                except OSError:
                    pass
    try:
        webbrowser.open(url, new=1)
    except Exception:
        pass


class BridgeState:
    """Thread-safe state connecting UDPDiscovery and TCPManager to the Zalo Web UI."""

    def __init__(self, name: str, tcp_port: int, udp_port: int, bcast_ip: str) -> None:
        self.name = name
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.downloads_dir = os.path.join(APP_DIR, DOWNLOADS_DIR)
        os.makedirs(self.downloads_dir, exist_ok=True)

        self._lock = threading.Lock()
        self._msg_seq = 0
        self.status = "online"
        self.histories: dict[str, list[dict[str, object]]] = {}
        self.unreads: dict[str, int] = {}
        self.known_tcp_peers: dict[str, dict[str, object]] = {}
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

    def _next_id(self) -> int:
        self._msg_seq += 1
        return self._msg_seq

    def _on_chat(self, sender: str, text: str) -> None:
        partner = self.tcp.get_current_partner() or sender
        key = partner if sender == self.name else sender
        with self._lock:
            self.histories.setdefault(key, []).append(
                {
                    "id": self._next_id(),
                    "sender": sender,
                    "text": text,
                    "time": self._now_str(),
                    "likes": 0,
                }
            )

    def _on_unread(self, sender: str, count: int) -> None:
        with self._lock:
            self.unreads[sender] = count
            self.known_tcp_peers.setdefault(
                sender,
                {"name": sender, "ip": "LAN", "tcp_port": 0, "status": "online"},
            )
            raw_hist = self.tcp._chat_histories.get(sender, [])
            if raw_hist:
                last_sender, last_text = raw_hist[-1]
                self.histories.setdefault(sender, []).append(
                    {
                        "id": self._next_id(),
                        "sender": last_sender,
                        "text": last_text,
                        "time": self._now_str(),
                        "likes": 0,
                    }
                )

    def _on_system(self, message: str) -> None:
        print(f"[*] {message}")
        if message.startswith("Received file '"):
            try:
                fname = message.split("'")[1]
                size_part = message.split("(")[1].split(")")[0]
                from_part = message.split(" from ")[1].split(" -> ")[0]
                safe_name = os.path.basename(fname)
                with self._lock:
                    self.known_tcp_peers.setdefault(
                        from_part,
                        {
                            "name": from_part,
                            "ip": "LAN",
                            "tcp_port": 0,
                            "status": "online",
                        },
                    )
                    self.histories.setdefault(from_part, []).append(
                        {
                            "id": self._next_id(),
                            "sender": from_part,
                            "text": f"📎 {safe_name}",
                            "file": {
                                "name": safe_name,
                                "size": size_part,
                                "url": f"/downloads/{urllib.parse.quote(safe_name)}",
                            },
                            "time": self._now_str(),
                            "likes": 0,
                        }
                    )
                    if self.tcp.get_current_partner() != from_part:
                        self.unreads[from_part] = self.unreads.get(from_part, 0) + 1
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

    def toggle_reaction(self, peer_name: str, msg_id: int) -> None:
        """Increment or toggle like reaction on a specific message."""
        with self._lock:
            msgs = self.histories.get(peer_name, [])
            for m in msgs:
                if m.get("id") == msg_id:
                    current = int(m.get("likes", 0))
                    m["likes"] = current + 1
                    break

    def snapshot(self) -> dict[str, object]:
        udp_peers = self.discovery.get_peers()
        peer_map: dict[str, dict[str, object]] = {}
        for p in udp_peers:
            peer_map[p.name] = {
                "name": p.name,
                "ip": p.ip,
                "tcp_port": p.tcp_port,
                "status": p.status,
            }
        with self._lock:
            for name, info in self.known_tcp_peers.items():
                if name not in peer_map:
                    peer_map[name] = info
            for name in list(self.tcp._connections.keys()):
                if name not in peer_map:
                    peer_map[name] = {
                        "name": name,
                        "ip": "LAN",
                        "tcp_port": 0,
                        "status": "online",
                    }
            return {
                "selfName": self.name,
                "selfStatus": self.status,
                "tcpPort": self.tcp_port,
                "udpPort": self.udp_port,
                "activePartner": self.tcp.get_current_partner(),
                "peers": list(peer_map.values()),
                "histories": self.histories,
                "unreads": self.unreads,
                "transfer": self.transfer,
            }


def make_handler(state: BridgeState):
    """Create an HTTP handler serving static fe/ assets, downloads/, and P2P API routes."""

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
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/state":
                self._send_json(state.snapshot())
                return

            if parsed.path.startswith("/downloads/"):
                rel_name = urllib.parse.unquote(parsed.path[len("/downloads/") :])
                safe_name = os.path.basename(rel_name)
                full_path = os.path.join(state.downloads_dir, safe_name)
                if not safe_name or not os.path.isfile(full_path):
                    self.send_error(HTTPStatus.NOT_FOUND, "File not found in downloads/")
                    return
                ctype, _ = mimetypes.guess_type(full_path)
                ctype = ctype or "application/octet-stream"
                try:
                    with open(full_path, "rb") as f:
                        data = f.read()
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header(
                        "Content-Disposition",
                        f"inline; filename*=UTF-8''{urllib.parse.quote(safe_name)}",
                    )
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
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

            if self.path == "/api/leave":
                state.tcp.leave_chat()
                self._send_json({"ok": True})
                return

            if self.path == "/api/send":
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                target = str(body.get("target", "")).strip()
                text = str(body.get("text", "")).strip()
                if target and state.tcp.get_current_partner() != target:
                    peer = state.discovery.resolve_peer(target) or PeerInfo(
                        name=target, ip="127.0.0.1", tcp_port=0
                    )
                    state.tcp.switch_chat(peer)
                    with state._lock:
                        state.unreads.pop(target, None)
                ok = state.tcp.send_chat(text) if text else False
                self._send_json({"ok": ok})
                return

            if self.path == "/api/react":
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                target = str(body.get("target", "")).strip()
                msg_id = int(body.get("msgId", 0))
                state.toggle_reaction(target, msg_id)
                self._send_json({"ok": True})
                return

            if self.path == "/api/status":
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                status = str(body.get("status", "online")).lower()
                if status in VALID_STATUSES:
                    state.discovery.set_status(status)
                    with state._lock:
                        state.status = status
                self._send_json({"ok": True})
                return

            if self.path == "/api/open_file":
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                safe_name = os.path.basename(str(body.get("filename", "")).strip())
                full_path = os.path.join(state.downloads_dir, safe_name)
                if not safe_name or not os.path.isfile(full_path):
                    self._send_json({"ok": False, "error": "File not found"}, status=404)
                    return
                opened = False
                if hasattr(os, "startfile"):
                    try:
                        os.startfile(full_path)
                        opened = True
                    except OSError:
                        opened = False
                self._send_json(
                    {
                        "ok": True,
                        "openedOnOS": opened,
                        "url": f"/downloads/{urllib.parse.quote(safe_name)}",
                    }
                )
                return

            if self.path == "/api/reveal_file":
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                safe_name = os.path.basename(str(body.get("filename", "")).strip())
                full_path = os.path.join(state.downloads_dir, safe_name)
                if os.path.isfile(full_path) and sys.platform.startswith("win"):
                    try:
                        subprocess.Popen(
                            ["explorer.exe", f"/select,{os.path.normpath(full_path)}"]
                        )
                    except OSError:
                        pass
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

                if target and state.tcp.get_current_partner() != target:
                    peer = state.discovery.resolve_peer(target) or PeerInfo(
                        name=target, ip="127.0.0.1", tcp_port=0
                    )
                    state.tcp.switch_chat(peer)

                safe_name = os.path.basename(file_name) or "upload.bin"
                os.makedirs(state.downloads_dir, exist_ok=True)
                saved_path = os.path.join(state.downloads_dir, safe_name)
                with open(saved_path, "wb") as f:
                    f.write(file_bytes)

                ok = state.tcp.send_file_async(saved_path)
                if ok:
                    size_str = _format_size(len(file_bytes))
                    with state._lock:
                        state.histories.setdefault(target, []).append(
                            {
                                "id": state._next_id(),
                                "sender": state.name,
                                "text": f"📎 {safe_name}",
                                "file": {
                                    "name": safe_name,
                                    "size": size_str,
                                    "url": f"/downloads/{urllib.parse.quote(safe_name)}",
                                },
                                "time": state._now_str(),
                                "likes": 0,
                            }
                        )
                self._send_json({"ok": ok, "filename": safe_name})
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
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open Chrome/web browser on startup",
    )
    args = parser.parse_args()

    state = BridgeState(args.name, args.port, args.udp_port, args.bcast)
    state.start()

    url = f"http://127.0.0.1:{args.web_port}"
    server = ThreadingHTTPServer(("127.0.0.1", args.web_port), make_handler(state))
    print(f"[*] Zalo Web UI running at: {url}")
    print(
        f"[*] P2P Node '{args.name}' — TCP port {args.port} | UDP port {args.udp_port}"
    )

    if not args.no_browser:
        threading.Timer(0.4, open_in_chrome_or_default, args=(url,)).start()

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
