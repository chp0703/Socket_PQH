"""Automated unit and integration tests for LAN Chat & File Sharing (P2P)."""

from __future__ import annotations

import hashlib
from http.server import ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from prompt_toolkit import PromptSession  # noqa: E402
from prompt_toolkit.application import create_app_session  # noqa: E402
from prompt_toolkit.input import create_pipe_input  # noqa: E402
from prompt_toolkit.output import DummyOutput  # noqa: E402
from prompt_toolkit.patch_stdout import patch_stdout  # noqa: E402

import console_ui  # noqa: E402
from fe.server import BridgeState, make_handler  # noqa: E402
import lanchat  # noqa: E402
import protocol  # noqa: E402
from tcp_manager import TCPManager  # noqa: E402
from udp_discovery import UDPDiscovery  # noqa: E402


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def _http_json(
    base_url: str, path: str, payload: dict[str, object] | None = None
) -> tuple[int, dict[str, object]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _build_demo_bmp() -> bytes:
    """Create a small valid 2x2 24-bit BMP image in memory."""
    row = b"\xff\x00\x00\x00\xff\x00\x00\x00"  # 2 pixels + 2 padding bytes
    pixel_data = row * 2
    file_size = 54 + len(pixel_data)
    header = (
        b"BM"
        + file_size.to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + (54).to_bytes(4, "little")
        + (40).to_bytes(4, "little")
        + (2).to_bytes(4, "little")
        + (2).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (24).to_bytes(2, "little")
        + (0).to_bytes(4, "little")
        + len(pixel_data).to_bytes(4, "little")
        + (2835).to_bytes(4, "little")
        + (2835).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
    )
    return header + pixel_data


class TestProtocol(unittest.TestCase):
    """Unit tests for protocol.py encoding, decoding, and TCP stream framing."""

    def test_hello_roundtrip_and_sanitization(self) -> None:
        raw = protocol.encode_hello(" Quan|A ", 5000, "AWAY")
        self.assertEqual(raw, b"HELLO|Quan_A|5000|away")
        self.assertEqual(protocol.decode_hello(raw), ("Quan_A", 5000, "away"))

    def test_hello_invalid_datagrams(self) -> None:
        bad_packets = [
            b"",
            b"PING|Quan|5000|online",
            b"HELLO|Quan|5000",
            b"HELLO|Quan|5000|online|extra",
            b"HELLO|   |5000|online",
            b"HELLO|Quan|0|online",
            b"HELLO|Quan|65536|online",
            b"HELLO|Quan|notaport|online",
            b"HELLO|Quan|5000|busy",
            b"\xff\xfe\xfd",
        ]
        for pkt in bad_packets:
            self.assertIsNone(protocol.decode_hello(pkt), f"Expected None for {pkt!r}")

    def test_peer_bye_and_clean_eof(self) -> None:
        a, b = socket.socketpair()
        try:
            a.sendall(protocol.encode_peer("Quan", 5000) + protocol.encode_bye())
            a.shutdown(socket.SHUT_WR)
            self.assertEqual(protocol.read_frame_header(b), ("PEER", "Quan", 5000))
            self.assertEqual(protocol.read_frame_header(b), ("BYE",))
            self.assertIsNone(protocol.read_frame_header(b))
        finally:
            a.close()
            b.close()

    def test_msg_utf8_and_concatenated_frames(self) -> None:
        text1 = "Chào bạn 👍"
        self.assertEqual(len(text1), 10)
        self.assertEqual(len(text1.encode("utf-8")), 16)
        text2 = "Khung thứ hai!"
        stream = protocol.encode_msg(text1) + b"\r\n" + protocol.encode_msg(text2)

        a, b = socket.socketpair()
        try:
            a.sendall(stream)
            a.shutdown(socket.SHUT_WR)

            h1 = protocol.read_frame_header(b)
            self.assertEqual(h1, ("MSG", 16))
            self.assertEqual(protocol.recv_exact(b, 16).decode("utf-8"), text1)

            h2 = protocol.read_frame_header(b)
            self.assertEqual(h2, ("MSG", len(text2.encode("utf-8"))))
            self.assertEqual(protocol.recv_exact(b, h2[1]).decode("utf-8"), text2)
            self.assertIsNone(protocol.read_frame_header(b))
        finally:
            a.close()
            b.close()

    def test_file_header_sanitization(self) -> None:
        hdr = protocol.encode_file_header("../../secret/my|photo.png", 12345)
        self.assertEqual(hdr, b"FILE|my_photo.png|12345|")
        a, b = socket.socketpair()
        try:
            a.sendall(hdr)
            a.shutdown(socket.SHUT_WR)
            self.assertEqual(
                protocol.read_frame_header(b), ("FILE", "my_photo.png", 12345)
            )
        finally:
            a.close()
            b.close()

    def test_header_field_limit_1024_bytes(self) -> None:
        oversized = b"MSG|" + (b"1" * 1025) + b"|"
        a, b = socket.socketpair()
        try:
            a.sendall(oversized)
            with self.assertRaises(ValueError):
                protocol.read_frame_header(b)
        finally:
            a.close()
            b.close()

    def test_premature_eof_in_header_and_recv_exact(self) -> None:
        a, b = socket.socketpair()
        try:
            a.sendall(b"MSG|10")
            a.close()
            with self.assertRaises(ConnectionError):
                protocol.read_frame_header(b)
        finally:
            b.close()

        a2, b2 = socket.socketpair()
        try:
            def writer() -> None:
                for part in (b"ab", b"cd", b"ef"):
                    time.sleep(0.02)
                    a2.sendall(part)
                a2.close()

            t = threading.Thread(target=writer, daemon=True)
            t.start()
            self.assertEqual(protocol.recv_exact(b2, 6), b"abcdef")
            with self.assertRaises(ConnectionError):
                protocol.recv_exact(b2, 4)
            t.join(timeout=1.0)
        finally:
            b2.close()


class TestUDPDiscovery(unittest.TestCase):
    """Integration tests for UDPDiscovery on loopback broadcast."""

    def test_two_instances_discovery_status_and_10s_timeout(self) -> None:
        udp_port = _free_udp_port()
        sys_a: list[str] = []
        sys_b: list[str] = []
        d_a = UDPDiscovery(
            "NodeA",
            51001,
            udp_port=udp_port,
            bcast_ip="127.255.255.255",
            on_system=sys_a.append,
        )
        d_b = UDPDiscovery(
            "NodeB",
            51002,
            udp_port=udp_port,
            bcast_ip="127.255.255.255",
            on_system=sys_b.append,
        )
        d_a.start()
        d_b.start()
        try:
            self.assertTrue(
                _wait_until(
                    lambda: len(d_a.get_peers()) == 1 and len(d_b.get_peers()) == 1,
                    timeout=5.0,
                )
            )
            self.assertIsNotNone(d_a.resolve_peer("1"))
            self.assertEqual(d_a.resolve_peer("nodeb").tcp_port, 51002)

            d_b.set_status("away")
            self.assertTrue(
                _wait_until(
                    lambda: d_a.get_peers()[0].status == "away",
                    timeout=3.0,
                )
            )
            self.assertTrue(any("NodeB is now away" in m for m in sys_a))

            d_b.stop()
            self.assertTrue(
                _wait_until(lambda: len(d_a.get_peers()) == 0, timeout=13.0)
            )
            self.assertTrue(any("went offline" in m for m in sys_a))
        finally:
            d_b.stop()
            d_a.stop()


class TestTCPManagerAndErrorHandling(unittest.TestCase):
    """Integration tests for multi-peer chat, unread, file transfer, and Section 5.3 errors."""

    def test_multi_peer_unread_switch_and_leave(self) -> None:
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2, tempfile.TemporaryDirectory() as d3:
            events_a: list[tuple] = []
            events_b: list[tuple] = []
            events_c: list[tuple] = []

            t_a = TCPManager(
                "NodeA",
                _free_tcp_port(),
                downloads_dir=d1,
                on_chat=lambda s, m: events_a.append(("chat", s, m)),
                on_system=lambda m: events_a.append(("sys", m)),
            )
            t_b = TCPManager(
                "NodeB",
                _free_tcp_port(),
                downloads_dir=d2,
                on_chat=lambda s, m: events_b.append(("chat", s, m)),
                on_unread=lambda s, c: events_b.append(("unread", s, c)),
                on_system=lambda m: events_b.append(("sys", m)),
            )
            t_c = TCPManager(
                "NodeC",
                _free_tcp_port(),
                downloads_dir=d3,
                on_chat=lambda s, m: events_c.append(("chat", s, m)),
                on_system=lambda m: events_c.append(("sys", m)),
            )
            t_a.start()
            t_b.start()
            t_c.start()
            try:
                peer_a = protocol.PeerInfo("NodeA", "127.0.0.1", t_a.listen_port)
                peer_b = protocol.PeerInfo("NodeB", "127.0.0.1", t_b.listen_port)
                peer_c = protocol.PeerInfo("NodeC", "127.0.0.1", t_c.listen_port)

                t_b.switch_chat(peer_a)
                self.assertTrue(
                    _wait_until(lambda: "NodeB" in t_a._connections, timeout=3.0)
                )
                t_a.switch_chat(peer_b)
                self.assertTrue(t_c.connect_peer(peer_b))
                self.assertTrue(t_c.switch_chat(peer_b) == [])
                self.assertTrue(t_c.send_chat("Chào bạn 👍"))
                self.assertTrue(t_c.send_chat("Tin thứ hai"))

                self.assertTrue(
                    _wait_until(
                        lambda: ("unread", "NodeC", 2) in events_b, timeout=3.0
                    )
                )
                # Active chat with NodeA still works while unread arrives from NodeC
                self.assertTrue(t_b.send_chat("Đang chat với A"))
                self.assertTrue(
                    _wait_until(
                        lambda: ("chat", "NodeB", "Đang chat với A") in events_a,
                        timeout=3.0,
                    )
                )

                unread = t_b.switch_chat(peer_c)
                self.assertEqual(
                    unread, [("NodeC", "Chào bạn 👍"), ("NodeC", "Tin thứ hai")]
                )
                self.assertTrue(t_b.send_chat("Đã nhận 2 tin"))
                self.assertTrue(
                    _wait_until(
                        lambda: ("chat", "NodeB", "Đã nhận 2 tin") in events_c,
                        timeout=3.0,
                    )
                )

                t_b.leave_chat()
                self.assertIsNone(t_b.get_current_partner())
                self.assertTrue(
                    _wait_until(
                        lambda: any(
                            ev[0] == "sys" and "Returned to main prompt" in ev[1]
                            for ev in events_c
                        ),
                        timeout=3.0,
                    )
                )
            finally:
                t_a.stop()
                t_b.stop()
                t_c.stop()

    def test_async_file_transfer_and_concurrent_chat(self) -> None:
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            progress_a: list[tuple[int, int]] = []
            events_a: list[tuple] = []
            events_b: list[tuple] = []

            t_a = TCPManager(
                "NodeA",
                _free_tcp_port(),
                downloads_dir=d1,
                on_chat=lambda s, m: events_a.append(("chat", s, m)),
                on_system=lambda m: events_a.append(("sys", m)),
                on_progress=lambda _lbl, cur, tot: progress_a.append((cur, tot)),
            )
            t_b = TCPManager(
                "NodeB",
                _free_tcp_port(),
                downloads_dir=d2,
                on_chat=lambda s, m: events_b.append(("chat", s, m)),
                on_system=lambda m: events_b.append(("sys", m)),
            )
            t_a.start()
            t_b.start()
            try:
                peer_b = protocol.PeerInfo("NodeB", "127.0.0.1", t_b.listen_port)
                peer_a = protocol.PeerInfo("NodeA", "127.0.0.1", t_a.listen_port)
                t_a.switch_chat(peer_b)
                self.assertTrue(
                    _wait_until(lambda: "NodeA" in t_b._connections, timeout=3.0)
                )
                t_b.switch_chat(peer_a)

                payload = os.urandom(262144)  # 256 KB
                src_path = os.path.join(d1, "test_256k.bin")
                with open(src_path, "wb") as f:
                    f.write(payload)

                self.assertTrue(t_a.send_file_async(src_path))
                self.assertTrue(t_b.send_chat("Tin nhắn song song khi đang truyền tệp"))

                dst_path = os.path.join(d2, "test_256k.bin")
                self.assertTrue(
                    _wait_until(
                        lambda: os.path.isfile(dst_path)
                        and os.path.getsize(dst_path) == len(payload)
                        and ("chat", "NodeB", "Tin nhắn song song khi đang truyền tệp")
                        in events_a,
                        timeout=5.0,
                    )
                )
                with open(dst_path, "rb") as f:
                    self.assertEqual(
                        hashlib.sha256(f.read()).hexdigest(),
                        hashlib.sha256(payload).hexdigest(),
                    )
                self.assertTrue(any(cur == len(payload) for cur, _ in progress_a))
            finally:
                t_a.stop()
                t_b.stop()

    def test_error_handling_offline_missing_interrupted_and_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as d1:
            errors: list[str] = []
            systems: list[str] = []
            t_b = TCPManager(
                "NodeB",
                _free_tcp_port(),
                downloads_dir=d1,
                on_error=errors.append,
                on_system=systems.append,
            )
            t_b.start()
            try:
                # 1. Offline peer (tcp_port=0 and closed port)
                self.assertFalse(
                    t_b.connect_peer(protocol.PeerInfo("Ghost", "127.0.0.1", 0))
                )
                closed_port = _free_tcp_port()
                self.assertFalse(
                    t_b.connect_peer(
                        protocol.PeerInfo("OfflinePeer", "127.0.0.1", closed_port)
                    )
                )
                self.assertTrue(any("not online" in e for e in errors))
                self.assertTrue(any("Cannot connect" in e for e in errors))

                # 2. Missing file
                t_b._current_partner = "FakePartner"
                t_b._connections["FakePartner"] = socket.socket()  # dummy placeholder
                t_b._send_locks["FakePartner"] = threading.Lock()
                try:
                    self.assertFalse(t_b.send_file_async("no_such_file_999.dat"))
                    self.assertTrue(any("File not found" in e for e in errors))
                finally:
                    t_b._connections.pop("FakePartner").close()
                    t_b._current_partner = None

                # 3. Interrupted file transfer deletes partial file
                raw = socket.create_connection(("127.0.0.1", t_b.listen_port), timeout=3.0)
                raw.sendall(
                    protocol.encode_peer("Rogue", 59999)
                    + protocol.encode_file_header("broken.bin", 10000)
                    + (b"X" * 2048)
                )
                raw.close()
                self.assertTrue(
                    _wait_until(
                        lambda: any("partial file deleted" in e for e in errors),
                        timeout=3.0,
                    )
                )
                self.assertFalse(os.path.exists(os.path.join(d1, "broken.bin")))

                # 4. Path traversal filename is stripped via basename
                raw2 = socket.create_connection(("127.0.0.1", t_b.listen_port), timeout=3.0)
                raw2.sendall(
                    protocol.encode_peer("SafeCheck", 59998)
                    + b"FILE|../escape.txt|5|hello"
                    + protocol.encode_bye()
                )
                raw2.close()
                safe_path = os.path.join(d1, "escape.txt")
                self.assertTrue(
                    _wait_until(lambda: os.path.isfile(safe_path), timeout=3.0)
                )
                self.assertFalse(
                    os.path.exists(os.path.join(os.path.dirname(d1), "escape.txt"))
                )
            finally:
                t_b.stop()


class _FakeUI:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def show_peers(self, peers) -> None:
        self.events.append(("peers", [p.name for p in peers]))

    def show_help(self) -> None:
        self.events.append(("help",))

    def print_system(self, msg: str) -> None:
        self.events.append(("sys", msg))

    def print_error(self, msg: str) -> None:
        self.events.append(("err", msg))

    def print_chat(self, sender: str, msg: str) -> None:
        self.events.append(("chat", sender, msg))


class _FakeDiscovery:
    def __init__(self, peers) -> None:
        self._peers = peers
        self.status = "online"

    def get_peers(self):
        return list(self._peers)

    def resolve_peer(self, target: str):
        if target == "1" and self._peers:
            return self._peers[0]
        for p in self._peers:
            if p.name.lower() == target.lower():
                return p
        return None

    def set_status(self, status: str) -> None:
        self.status = status


class _FakeTCP:
    def __init__(self) -> None:
        self.partner: str | None = None
        self.sent: list[str] = []
        self.files: list[str] = []

    def switch_chat(self, peer):
        self.partner = peer.name
        return [("Minh", "unread 1")]

    def get_current_partner(self):
        return self.partner

    def send_chat(self, text: str) -> bool:
        self.sent.append(text)
        return True

    def send_file_async(self, path: str) -> bool:
        self.files.append(path)
        return True

    def leave_chat(self) -> None:
        self.partner = None


class TestCLICommandsAndUI(unittest.TestCase):
    """Tests for all 8 CLI commands, ConsoleUI rendering, and prompt_toolkit redraw."""

    def test_all_eight_commands_and_invalid_command(self) -> None:
        ui = _FakeUI()
        disc = _FakeDiscovery([protocol.PeerInfo("Minh", "192.168.1.12", 5000)])
        tcp = _FakeTCP()

        self.assertTrue(lanchat.handle_command("/list", ui, disc, tcp))
        self.assertTrue(lanchat.handle_command("/chat 1", ui, disc, tcp))
        self.assertTrue(lanchat.handle_command("Xin chào", ui, disc, tcp))
        self.assertTrue(lanchat.handle_command("/send slides.pdf", ui, disc, tcp))
        self.assertTrue(lanchat.handle_command("/status away", ui, disc, tcp))
        self.assertTrue(lanchat.handle_command("/status bad", ui, disc, tcp))
        self.assertTrue(lanchat.handle_command("/help", ui, disc, tcp))
        self.assertTrue(lanchat.handle_command("/leave", ui, disc, tcp))
        self.assertTrue(lanchat.handle_command("/unknown", ui, disc, tcp))
        self.assertFalse(lanchat.handle_command("/quit", ui, disc, tcp))

        self.assertEqual(tcp.sent, ["Xin chào"])
        self.assertEqual(tcp.files, ["slides.pdf"])
        self.assertEqual(disc.status, "away")
        self.assertIsNone(tcp.partner)
        self.assertIn(("peers", ["Minh"]), ui.events)
        self.assertIn(("chat", "Minh", "unread 1"), ui.events)
        self.assertIn(("help",), ui.events)
        self.assertTrue(
            any(e[0] == "err" and "Invalid command" in e[1] for e in ui.events)
        )

    def test_prompt_toolkit_typing_preserved_when_message_arrives(self) -> None:
        out_buf = io.StringIO()
        with create_pipe_input() as pipe_in:
            with create_app_session(input=pipe_in, output=DummyOutput()):
                with patch_stdout(raw=True):
                    session: PromptSession[str] = PromptSession(
                        input=pipe_in, output=DummyOutput()
                    )
                    ui = console_ui.ConsoleUI("> ")
                    ui._session = session
                    ui._console = console_ui.Console(file=out_buf, highlight=False)

                    result: list[str] = []

                    def reader() -> None:
                        result.append(ui.read_line())

                    t = threading.Thread(target=reader, daemon=True)
                    t.start()
                    time.sleep(0.1)
                    pipe_in.send_text("you can che")
                    time.sleep(0.1)
                    ui.print_chat("Minh", "ok, which part?")
                    time.sleep(0.1)
                    pipe_in.send_text("\r")
                    t.join(timeout=3.0)
                    ui.close()

        self.assertEqual(result, ["you can che"])
        self.assertIn("[Minh]", out_buf.getvalue())
        self.assertIn("ok, which part?", out_buf.getvalue())

    def test_console_ui_tables_and_tqdm(self) -> None:
        buf = io.StringIO()
        ui = console_ui.ConsoleUI("> ")
        ui._console = console_ui.Console(file=buf, highlight=False, width=100)
        try:
            ui.show_peers([protocol.PeerInfo("Minh", "127.0.0.1", 5000, "online")])
            ui.show_help()
            ui.update_progress("Sending demo.bin", 4096, 8192)
            ui.print_system("Notice while progress bar active")
            ui.update_progress("Sending demo.bin", 8192, 8192)
        finally:
            ui.close()
        text = buf.getvalue()
        self.assertIn("Minh", text)
        self.assertIn("/send <file>", text)

    def test_two_cli_subprocesses_end_to_end(self) -> None:
        udp_port = _free_udp_port()
        tcp_a = _free_tcp_port()
        tcp_b = _free_tcp_port()
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")

        proc_b = subprocess.Popen(
            [
                sys.executable,
                str(APP_DIR / "lanchat.py"),
                "--name",
                "CliB",
                "--port",
                str(tcp_b),
                "--udp-port",
                str(udp_port),
                "--bcast",
                "127.255.255.255",
            ],
            cwd=str(APP_DIR),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
        )
        proc_a = subprocess.Popen(
            [
                sys.executable,
                str(APP_DIR / "lanchat.py"),
                "--name",
                "CliA",
                "--port",
                str(tcp_a),
                "--udp-port",
                str(udp_port),
                "--bcast",
                "127.255.255.255",
            ],
            cwd=str(APP_DIR),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
        )
        try:
            time.sleep(1.5)
            assert proc_a.stdin is not None and proc_b.stdin is not None
            for cmd in (
                "/list\n",
                "/help\n",
                "/status away\n",
                "/chat CliB\n",
                "Hello CliB\n",
                "/leave\n",
                "/quit\n",
            ):
                proc_a.stdin.write(cmd)
                proc_a.stdin.flush()
                time.sleep(0.25)

            out_a, err_a = proc_a.communicate(timeout=5.0)
            proc_b.stdin.write("/chat CliA\n/quit\n")
            proc_b.stdin.flush()
            out_b, err_b = proc_b.communicate(timeout=5.0)

            self.assertEqual(proc_a.returncode, 0, err_a)
            self.assertEqual(proc_b.returncode, 0, err_b)
            self.assertIn("CliB", out_a)
            self.assertIn("Connected to CliB", out_a)
            self.assertIn("[CliA] Hello CliB", out_a)
            self.assertIn("New message from CliA (1 unread)", out_b)
            self.assertIn("[CliA] Hello CliB", out_b)
        finally:
            for p in (proc_a, proc_b):
                if p.poll() is None:
                    p.kill()
                    p.wait(timeout=2.0)


class TestWebUIBridge(unittest.TestCase):
    """End-to-end HTTP + P2P integration tests for fe/server.py."""

    def test_two_web_nodes_chat_like_and_file_transfer(self) -> None:
        udp_port = _free_udp_port()
        tcp_a = _free_tcp_port()
        tcp_b = _free_tcp_port()
        web_a = _free_tcp_port()
        web_b = _free_tcp_port()

        with tempfile.TemporaryDirectory() as d_a, tempfile.TemporaryDirectory() as d_b:
            state_a = BridgeState("NodeA", tcp_a, udp_port, "127.255.255.255")
            state_b = BridgeState("NodeB", tcp_b, udp_port, "127.255.255.255")
            state_a.downloads_dir = d_a
            state_a.tcp.downloads_dir = d_a
            state_b.downloads_dir = d_b
            state_b.tcp.downloads_dir = d_b

            state_a.start()
            state_b.start()
            srv_a = ThreadingHTTPServer(("127.0.0.1", web_a), make_handler(state_a))
            srv_b = ThreadingHTTPServer(("127.0.0.1", web_b), make_handler(state_b))
            th_a = threading.Thread(target=srv_a.serve_forever, daemon=True)
            th_b = threading.Thread(target=srv_b.serve_forever, daemon=True)
            th_a.start()
            th_b.start()
            url_a = f"http://127.0.0.1:{web_a}"
            url_b = f"http://127.0.0.1:{web_b}"

            try:
                self.assertTrue(
                    _wait_until(
                        lambda: any(
                            p["name"] == "NodeB"
                            for p in _http_json(url_a, "/api/state")[1]["peers"]
                        )
                        and any(
                            p["name"] == "NodeA"
                            for p in _http_json(url_b, "/api/state")[1]["peers"]
                        ),
                        timeout=5.0,
                    )
                )

                _http_json(url_b, "/api/status", {"status": "away"})
                self.assertTrue(
                    _wait_until(
                        lambda: any(
                            p["name"] == "NodeB" and p["status"] == "away"
                            for p in _http_json(url_a, "/api/state")[1]["peers"]
                        ),
                        timeout=3.0,
                    )
                )

                _http_json(url_a, "/api/chat", {"target": "NodeB"})
                _http_json(url_a, "/api/send", {"target": "NodeB", "text": "Chào bạn 👍"})
                self.assertTrue(
                    _wait_until(
                        lambda: _http_json(url_b, "/api/state")[1]["unreads"].get("NodeA")
                        == 1,
                        timeout=3.0,
                    )
                )

                _http_json(url_b, "/api/chat", {"target": "NodeA"})
                snap_b = _http_json(url_b, "/api/state")[1]
                self.assertEqual(snap_b["unreads"].get("NodeA", 0), 0)
                msg_id = snap_b["histories"]["NodeA"][0]["id"]
                _http_json(url_b, "/api/react", {"target": "NodeA", "msgId": msg_id})
                snap_b_liked = _http_json(url_b, "/api/state")[1]
                snap_a = _http_json(url_a, "/api/state")[1]
                self.assertEqual(snap_b_liked["histories"]["NodeA"][0]["likes"], 1)
                self.assertEqual(snap_a["histories"]["NodeB"][0]["likes"], 0)

                bmp_bytes = _build_demo_bmp()
                boundary = "----TestBoundary74f6186f"
                body = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="target"\r\n\r\n'
                    f"NodeB\r\n"
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="file"; filename="demo.bmp"\r\n'
                    f"Content-Type: image/bmp\r\n\r\n"
                ).encode("utf-8") + bmp_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
                req = urllib.request.Request(
                    f"{url_a}/api/send_file",
                    data=body,
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    self.assertEqual(resp.status, 200)

                recv_file = os.path.join(d_b, "demo.bmp")
                self.assertTrue(
                    _wait_until(
                        lambda: os.path.isfile(recv_file)
                        and any(
                            m.get("file", {}).get("name") == "demo.bmp"
                            for m in _http_json(url_b, "/api/state")[1]["histories"].get(
                                "NodeA", []
                            )
                        ),
                        timeout=5.0,
                    )
                )
                with open(recv_file, "rb") as f:
                    self.assertEqual(f.read(), bmp_bytes)

                with urllib.request.urlopen(f"{url_b}/downloads/demo.bmp", timeout=5.0) as dl:
                    self.assertIn("image", dl.headers.get("Content-Type", ""))
                    self.assertIn("inline", dl.headers.get("Content-Disposition", ""))
                    self.assertEqual(dl.read(), bmp_bytes)

                _http_json(url_a, "/api/leave", {})
                self.assertIsNone(_http_json(url_a, "/api/state")[1]["activePartner"])
            finally:
                srv_a.shutdown()
                srv_b.shutdown()
                srv_a.server_close()
                srv_b.server_close()
                state_a.stop()
                state_b.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)
