"""Console UI using prompt_toolkit (patch_stdout), rich tables, and tqdm progress bars."""

from __future__ import annotations

from contextlib import ExitStack
import sys
import threading

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.table import Table
from tqdm import tqdm

from protocol import PeerInfo


class ConsoleUI:
    """Thread-safe terminal interface that preserves user typing when messages arrive."""

    def __init__(self, prompt_text: str = "> ") -> None:
        self.prompt_text = prompt_text
        self._lock = threading.Lock()
        self._console = Console(file=sys.stdout, highlight=False)
        self._progress_bars: dict[str, tqdm] = {}

        self._session: PromptSession[str] | None = None
        self._patch_stack = ExitStack()
        if (
            sys.stdin is not None
            and sys.stdout is not None
            and sys.stdin.isatty()
            and sys.stdout.isatty()
        ):
            try:
                self._patch_stack.enter_context(patch_stdout(raw=True))
                self._session = PromptSession()
            except Exception:
                self._patch_stack.close()
                self._session = None

    def close(self) -> None:
        """Close active progress bars and release stdout patch context."""
        with self._lock:
            for bar in self._progress_bars.values():
                try:
                    bar.close()
                except Exception:
                    pass
            self._progress_bars.clear()
        try:
            self._patch_stack.close()
        except Exception:
            pass

    def _print_with_bars_paused(self, renderable: object) -> None:
        """Clear active tqdm bars, print via rich Console, and refresh active bars."""
        for bar in self._progress_bars.values():
            try:
                bar.clear()
            except Exception:
                pass
        self._console.print(renderable)
        for bar in self._progress_bars.values():
            try:
                bar.refresh()
            except Exception:
                pass

    def read_line(self) -> str:
        """Read a single input line from the user without breaking concurrent output."""
        if self._session is not None:
            return self._session.prompt(self.prompt_text)
        sys.stdout.write(self.prompt_text)
        sys.stdout.flush()
        line = sys.stdin.readline()
        if line == "":
            raise EOFError
        return line.rstrip("\r\n")

    def print_system(self, message: str) -> None:
        """Print a system notification line prefixed with [*]."""
        with self._lock:
            self._print_with_bars_paused(f"[bold cyan][*][/bold cyan] {message}")

    def print_chat(self, sender: str, message: str) -> None:
        """Print a chat message line prefixed with [sender]."""
        with self._lock:
            self._print_with_bars_paused(
                f"[bold green][{sender}][/bold green] {message}"
            )

    def print_error(self, message: str) -> None:
        """Print an error notification line prefixed with [!]."""
        with self._lock:
            self._print_with_bars_paused(f"[bold red][!] {message}[/bold red]")

    def show_peers(self, peers: list[PeerInfo]) -> None:
        """Render the online peers list using a formatted rich table."""
        with self._lock:
            if not peers:
                self._print_with_bars_paused(
                    "[bold cyan][*][/bold cyan] No other users online."
                )
                return
            table = Table(
                title="Online Users", show_header=True, header_style="bold magenta"
            )
            table.add_column("#", justify="right", style="cyan", no_wrap=True)
            table.add_column("Name", style="bold white")
            table.add_column("IP Address", style="white")
            table.add_column("TCP Port", justify="right", style="white")
            table.add_column("Status", style="bold")

            for idx, peer in enumerate(peers, start=1):
                status_style = "green" if peer.status == "online" else "yellow"
                table.add_row(
                    str(idx),
                    peer.name,
                    peer.ip,
                    str(peer.tcp_port),
                    f"[{status_style}]{peer.status}[/{status_style}]",
                )
            self._print_with_bars_paused(table)

    def show_help(self) -> None:
        """Render all supported CLI commands in a rich table."""
        commands = [
            ("/list", "Show online users with number, name, IP, port, and status"),
            ("/chat <name|number>", "Open or switch chat with the selected user (TCP)"),
            ("<any text>", "Send a message to the current chat partner"),
            ("/send <file>", "Send a file to the current chat partner"),
            ("/leave", "Close the current chat"),
            ("/status <online|away>", "Change your status (sent via UDP)"),
            ("/help", "Show all commands"),
            ("/quit", "Exit the program"),
        ]
        with self._lock:
            table = Table(
                title="Available Commands", show_header=True, header_style="bold cyan"
            )
            table.add_column("Command", style="bold yellow", no_wrap=True)
            table.add_column("Description", style="white")
            for cmd, desc in commands:
                table.add_row(cmd, desc)
            self._print_with_bars_paused(table)

    def update_progress(self, label: str, current: int, total: int) -> None:
        """Update or complete a tqdm progress bar for file transfer."""
        with self._lock:
            if total <= 0:
                return
            bar = self._progress_bars.get(label)
            if bar is None:
                bar = tqdm(
                    total=total,
                    desc=f"[*] {label}",
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    file=sys.stdout,
                    leave=False,
                    dynamic_ncols=True,
                )
                self._progress_bars[label] = bar

            delta = current - bar.n
            if delta > 0:
                bar.update(delta)

            if current >= total:
                self._progress_bars.pop(label, None)
                bar.close()
