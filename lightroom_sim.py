#!/usr/bin/env python3
"""
Lightroom Simulation Server

A fake Lightroom socket server that the Launchpad mapper can connect to
for testing without an actual Adobe Lightroom installation.

Usage:
    python3 lightroom_sim.py [--port PORT] [--web] [--web-port WEB_PORT]

The simulator:
- Listens on the same port as real Lightroom (default: 55555)
- Accepts connections from the Launchpad mapper
- Parses and logs all received commands (slider moves, button presses)
- Maintains simulated Lightroom state (develop parameters)
- Displays a live terminal UI showing current state
- Supports bidirectional communication (can send responses back)
"""

import argparse
import json
import os
import queue
import select
import socket
import sys
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# SIMULATED LIGHTROOM STATE
# =============================================================================

DEFAULT_DEVELOP_PARAMS = OrderedDict([
    ("exposure", 0.0),
    ("contrast", 0),
    ("highlights", 0),
    ("shadows", 0),
    ("whites", 0),
    ("blacks", 0),
    ("clarity", 0),
    ("vibrance", 0),
    ("saturation", 0),
    ("temperature", 6500),
    ("tint", 0),
    ("sharpness", 40),
    ("noise_reduction", 0),
])


class LightroomState:
    """Maintains simulated Lightroom develop module state."""

    def __init__(self):
        self.params: Dict[str, float] = dict(DEFAULT_DEVELOP_PARAMS)
        self.command_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.connected_clients: int = 0
        self.total_commands: int = 0
        self.last_command_time: Optional[float] = None

    def process_command(self, raw: str) -> Optional[str]:
        """
        Process a command from the mapper and return optional response.

        Supported formats:
        - Numeric IDs: "1", "57", etc. (button presses / dofile actions)
        - Slider values: "set_<param>:<value>" (e.g. "set_exposure:1.5")
        """
        raw = raw.strip()
        if not raw:
            return None

        with self._lock:
            self.total_commands += 1
            self.last_command_time = time.time()

            entry = {
                "time": time.strftime("%H:%M:%S"),
                "raw": raw,
                "type": "unknown",
                "detail": "",
            }

            if raw.startswith("set_"):
                # Slider command: set_<param>:<value>
                parts = raw.split(":", 1)
                if len(parts) == 2:
                    param_name = parts[0][4:]  # strip "set_"
                    try:
                        value = float(parts[1])
                        old_value = self.params.get(param_name, 0)
                        self.params[param_name] = value
                        entry["type"] = "slider"
                        entry["detail"] = f"{param_name}: {old_value} → {value}"
                    except ValueError:
                        entry["type"] = "slider_error"
                        entry["detail"] = f"Invalid value: {parts[1]}"
                else:
                    entry["type"] = "slider_error"
                    entry["detail"] = f"Malformed: {raw}"
            else:
                # Numeric / discrete command
                entry["type"] = "button"
                entry["detail"] = f"Command ID: {raw}"

            self.command_log.append(entry)
            # Keep last 200 entries
            if len(self.command_log) > 200:
                self.command_log = self.command_log[-200:]

            return None  # No response needed for now

    def get_snapshot(self) -> Dict[str, Any]:
        """Get current state snapshot."""
        with self._lock:
            return {
                "params": dict(self.params),
                "connected_clients": self.connected_clients,
                "total_commands": self.total_commands,
                "last_command_time": self.last_command_time,
                "recent_log": list(self.command_log[-20:]),
            }

    def reset(self):
        """Reset all parameters to defaults."""
        with self._lock:
            self.params = dict(DEFAULT_DEVELOP_PARAMS)
            self.command_log.clear()
            self.total_commands = 0


# =============================================================================
# SOCKET SERVER
# =============================================================================

class LightroomSimServer:
    """TCP server that mimics Lightroom's socket interface."""

    def __init__(self, host: str = "127.0.0.1", port: int = 55555):
        self.host = host
        self.port = port
        self.state = LightroomState()
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._clients: List[socket.socket] = []
        self._clients_lock = threading.Lock()
        self._event_queue: queue.Queue = queue.Queue()

    def start(self):
        """Start the simulation server."""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.settimeout(1.0)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(5)
        self._running = True

        thread = threading.Thread(target=self._accept_loop, daemon=True)
        thread.start()

        self._event_queue.put(("server_start", f"Listening on {self.host}:{self.port}"))

    def stop(self):
        """Stop the server and close all connections."""
        self._running = False
        with self._clients_lock:
            for c in self._clients:
                try:
                    c.close()
                except OSError:
                    pass
            self._clients.clear()
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
        self._event_queue.put(("server_stop", "Server stopped"))

    def send_to_clients(self, message: str):
        """Send a message to all connected clients (sim → mapper)."""
        data = (message if message.endswith("\n") else message + "\n").encode("utf-8")
        with self._clients_lock:
            dead = []
            for c in self._clients:
                try:
                    c.sendall(data)
                except OSError:
                    dead.append(c)
            for c in dead:
                self._clients.remove(c)

    def _accept_loop(self):
        """Accept incoming connections."""
        while self._running:
            try:
                client, addr = self._server_socket.accept()
                client.settimeout(0.1)
                with self._clients_lock:
                    self._clients.append(client)
                    self.state.connected_clients = len(self._clients)
                self._event_queue.put(("connect", f"Client connected: {addr[0]}:{addr[1]}"))
                thread = threading.Thread(
                    target=self._handle_client, args=(client, addr), daemon=True
                )
                thread.start()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    self._event_queue.put(("error", "Accept error"))
                break

    def _handle_client(self, client: socket.socket, addr: Tuple[str, int]):
        """Handle a single client connection."""
        buffer = ""
        try:
            while self._running:
                try:
                    data = client.recv(4096)
                    if not data:
                        break
                    buffer += data.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            response = self.state.process_command(line)
                            if response:
                                client.sendall((response + "\n").encode("utf-8"))
                            self._event_queue.put(("command", line))
                except socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            with self._clients_lock:
                if client in self._clients:
                    self._clients.remove(client)
                self.state.connected_clients = len(self._clients)
            try:
                client.close()
            except OSError:
                pass
            self._event_queue.put(("disconnect", f"Client disconnected: {addr[0]}:{addr[1]}"))

    def get_events(self, timeout: float = 0.1) -> List[Tuple[str, str]]:
        """Get pending events from the queue."""
        events = []
        try:
            while True:
                events.append(self._event_queue.get_nowait())
        except queue.Empty:
            pass
        return events


# =============================================================================
# TERMINAL UI
# =============================================================================

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def render_terminal_ui(server: LightroomSimServer):
    """Render a simple terminal dashboard."""
    snap = server.state.get_snapshot()

    lines = []
    lines.append("=" * 60)
    lines.append("  🎨 LIGHTROOM SIMULATOR")
    lines.append("=" * 60)
    lines.append(f"  Status: {'🟢 Running' if server._running else '🔴 Stopped'}")
    lines.append(f"  Clients: {snap['connected_clients']}  |  Commands: {snap['total_commands']}")
    if snap["last_command_time"]:
        ago = time.time() - snap["last_command_time"]
        lines.append(f"  Last command: {ago:.1f}s ago")
    lines.append("")
    lines.append("  --- Develop Parameters ---")

    for param, value in snap["params"].items():
        bar_len = 20
        # Normalize for display (most params -100 to 100, exposure -5 to 5)
        if param == "exposure":
            norm = (value + 5) / 10
        elif param == "temperature":
            norm = (value - 2000) / 10000
        elif param == "sharpness":
            norm = value / 150
        else:
            norm = (value + 100) / 200
        norm = max(0, min(1, norm))
        filled = int(norm * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        lines.append(f"  {param:>18s}: [{bar}] {value:>8.1f}")

    lines.append("")
    lines.append("  --- Recent Commands ---")
    for entry in snap["recent_log"][-10:]:
        icon = "🎚️" if entry["type"] == "slider" else "🔘"
        lines.append(f"  {icon} [{entry['time']}] {entry['detail']}")

    lines.append("")
    lines.append("  [r]eset params  [q]uit  [s]end test message")
    lines.append("=" * 60)

    clear_screen()
    print("\n".join(lines))


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Lightroom Simulation Server")
    parser.add_argument("--host", default="127.0.0.1", help="Listen host")
    parser.add_argument("--port", type=int, default=55555, help="Listen port")
    parser.add_argument("--headless", action="store_true", help="No terminal UI")
    args = parser.parse_args()

    server = LightroomSimServer(host=args.host, port=args.port)
    server.start()

    print(f"Lightroom Simulator listening on {args.host}:{args.port}")
    print("Waiting for Launchpad mapper to connect...")

    if args.headless:
        # Headless mode: just log events
        try:
            while True:
                events = server.get_events(timeout=1.0)
                for etype, detail in events:
                    print(f"[{etype}] {detail}")
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    else:
        # Interactive terminal UI
        import sys
        import select as sel

        try:
            while True:
                render_terminal_ui(server)
                # Check for keyboard input (non-blocking on Unix)
                if sys.platform != "win32":
                    import termios
                    import tty

                    old = termios.tcgetattr(sys.stdin)
                    try:
                        tty.setcbreak(sys.stdin.fileno())
                        rlist, _, _ = sel.select([sys.stdin], [], [], 0.5)
                        if rlist:
                            ch = sys.stdin.read(1)
                            if ch == "q":
                                break
                            elif ch == "r":
                                server.state.reset()
                            elif ch == "s":
                                server.send_to_clients("ping")
                    finally:
                        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
                else:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    server.stop()
    print("\nSimulator stopped.")


if __name__ == "__main__":
    main()
