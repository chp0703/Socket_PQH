"""Main CLI entry point for LAN Chat & File Sharing (P2P)."""

from __future__ import annotations

import argparse
import os
import sys

from console_ui import ConsoleUI
from protocol import (
    DEFAULT_BCAST,
    DEFAULT_TCP_PORT,
    DOWNLOADS_DIR,
    UDP_PORT,
    VALID_STATUSES,
    PeerInfo,
)
from tcp_manager import TCPManager
from udp_discovery import UDPDiscovery


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="LAN Chat & File Sharing (P2P) using UDP Discovery and TCP Sockets."
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Your display name on the LAN (e.g. Quan, Minh).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_TCP_PORT,
        help=f"TCP listening port (default: {DEFAULT_TCP_PORT}).",
    )
    parser.add_argument(
        "--bcast",
        default=DEFAULT_BCAST,
        help=f"UDP broadcast address (default: {DEFAULT_BCAST}; use 127.255.255.255 if offline).",
    )
    parser.add_argument(
        "--udp-port",
        type=int,
        default=UDP_PORT,
        help=f"UDP discovery port (default: {UDP_PORT}).",
    )
    return parser.parse_args(argv)


def handle_command(
    raw_line: str,
    ui: ConsoleUI,
    discovery: UDPDiscovery,
    tcp: TCPManager,
) -> bool:
    """Process one user input line. Returns False when the user requests /quit."""
    line = raw_line.strip()
    if not line:
        return True

    if not line.startswith("/"):
        tcp.send_chat(line)
        return True

    parts = line.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/list":
        ui.show_peers(discovery.get_peers())
        return True

    if cmd == "/chat":
        if not arg:
            ui.print_error("Usage: /chat <name|number>")
            return True
        peer = discovery.resolve_peer(arg)
        if peer is None:
            # Allow switching to a peer that already has an open incoming TCP session or unread messages
            peer = PeerInfo(name=arg, ip="127.0.0.1", tcp_port=0)
            unread = tcp.switch_chat(peer)
            if tcp.get_current_partner() != arg and not unread:
                return True
        else:
            unread = tcp.switch_chat(peer)

        for sender, msg in unread:
            ui.print_chat(sender, msg)
        return True

    if cmd == "/send":
        if not arg:
            ui.print_error("Usage: /send <file>")
            return True
        tcp.send_file_async(arg)
        return True

    if cmd == "/leave":
        tcp.leave_chat()
        return True

    if cmd == "/status":
        status = arg.lower()
        if status not in VALID_STATUSES:
            ui.print_error("Usage: /status <online|away>")
            return True
        discovery.set_status(status)
        ui.print_system(f"Status set to {status}")
        return True

    if cmd == "/help":
        ui.show_help()
        return True

    if cmd == "/quit":
        ui.print_system("Shutting down...")
        return False

    ui.print_error(f"Invalid command '{cmd}'. Type /help to see all commands.")
    return True


def main(argv: list[str] | None = None) -> int:
    """Start UDP discovery, TCP manager, and interactive CLI loop."""
    args = parse_args(argv)
    name = args.name.strip().replace("|", "_")
    if not name:
        print("[!] Error: --name cannot be empty.", file=sys.stderr)
        return 1
    if not (1 <= args.port <= 65535):
        print(f"[!] Error: Invalid TCP port {args.port}.", file=sys.stderr)
        return 1

    base_dir = os.path.dirname(os.path.abspath(__file__))
    downloads_path = os.path.join(base_dir, DOWNLOADS_DIR)

    ui = ConsoleUI(prompt_text="> ")
    tcp = TCPManager(
        name=name,
        listen_port=args.port,
        downloads_dir=downloads_path,
        on_chat=ui.print_chat,
        on_unread=lambda sender, count: ui.print_system(
            f"New message from {sender} ({count} unread)"
        ),
        on_system=ui.print_system,
        on_error=ui.print_error,
        on_progress=ui.update_progress,
    )
    discovery = UDPDiscovery(
        name=name,
        tcp_port=args.port,
        udp_port=args.udp_port,
        bcast_ip=args.bcast,
        on_system=ui.print_system,
    )

    try:
        tcp.start()
    except OSError as exc:
        ui.print_error(
            f"Could not bind TCP port {args.port}: {exc}. Try another --port."
        )
        ui.close()
        return 1

    try:
        discovery.start()
    except OSError as exc:
        ui.print_error(f"Could not bind UDP port {args.udp_port}: {exc}")
        tcp.stop()
        ui.close()
        return 1

    ui.print_system(f"Listening on TCP port {args.port}")
    ui.print_system(f"Broadcasting presence on UDP port {args.udp_port}")

    try:
        while True:
            try:
                line = ui.read_line()
            except (EOFError, KeyboardInterrupt):
                ui.print_system("Exiting...")
                break
            if not handle_command(line, ui, discovery, tcp):
                break
    finally:
        discovery.stop()
        tcp.stop()
        ui.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
