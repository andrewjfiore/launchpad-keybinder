#!/usr/bin/env python3
"""
Persistent socket connection manager for Lightroom communication.
Provides efficient, keep-alive connections instead of per-message connections.
"""

import os
import queue
import socket
import threading
import time
from typing import Callable, List, Optional

# Configuration from environment or defaults
LIGHTROOM_SOCKET_HOST = os.getenv("LR_SOCKET_HOST", "127.0.0.1")
LIGHTROOM_SOCKET_PORT = int(os.getenv("LR_SOCKET_PORT", "55555"))


class LightroomSocketManager:
    """
    Manages a persistent socket connection to Lightroom.

    Features:
    - Keep-alive connection to avoid connection overhead per message
    - Automatic reconnection on failure
    - Thread-safe message queue for high-frequency commands
    - Batching support for slider movements
    """

    def __init__(
        self,
        host: str = LIGHTROOM_SOCKET_HOST,
        port: int = LIGHTROOM_SOCKET_PORT,
        connect_timeout: float = 2.0,
        send_timeout: float = 0.5,
        max_reconnect_attempts: int = 3,
        reconnect_delay: float = 0.5,
    ):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.send_timeout = send_timeout
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay

        # Connection state
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._lock = threading.RLock()

        # Message queue for async sending
        self._message_queue: queue.Queue = queue.Queue(maxsize=1000)
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Statistics
        self._messages_sent = 0
        self._messages_failed = 0
        self._reconnect_count = 0

        # Callbacks
        self._on_connect_callbacks: List[Callable] = []
        self._on_disconnect_callbacks: List[Callable] = []
        self._on_error_callbacks: List[Callable[[str], None]] = []

    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================

    def connect(self) -> bool:
        """
        Establish connection to Lightroom.

        Returns:
            True if connection succeeded, False otherwise
        """
        with self._lock:
            if self._connected and self._socket:
                return True

            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self.connect_timeout)
                self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                # Enable keep-alive
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

                self._socket.connect((self.host, self.port))
                self._socket.settimeout(self.send_timeout)
                self._connected = True

                self._notify_connect()
                print(f"Connected to Lightroom at {self.host}:{self.port}")
                return True

            except ConnectionRefusedError:
                self._handle_error("Lightroom is not listening. Is the plugin running?")
                self._cleanup_socket()
                return False

            except socket.timeout:
                self._handle_error(f"Connection timeout to Lightroom at {self.host}:{self.port}")
                self._cleanup_socket()
                return False

            except OSError as e:
                self._handle_error(f"Socket error connecting to Lightroom: {e}")
                self._cleanup_socket()
                return False

    def disconnect(self):
        """Close the connection to Lightroom."""
        with self._lock:
            if self._socket:
                try:
                    self._socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self._cleanup_socket()
            self._notify_disconnect()
            print("Disconnected from Lightroom")

    def _cleanup_socket(self):
        """Clean up socket resources."""
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        self._connected = False

    def reconnect(self) -> bool:
        """
        Attempt to reconnect with retry logic.

        Returns:
            True if reconnection succeeded, False otherwise
        """
        with self._lock:
            self._cleanup_socket()

            for attempt in range(1, self.max_reconnect_attempts + 1):
                print(f"Reconnecting to Lightroom (attempt {attempt}/{self.max_reconnect_attempts})...")
                if self.connect():
                    self._reconnect_count += 1
                    return True

                if attempt < self.max_reconnect_attempts:
                    time.sleep(self.reconnect_delay * attempt)

            return False

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        with self._lock:
            return self._connected and self._socket is not None

    # =========================================================================
    # MESSAGE SENDING
    # =========================================================================

    def send(self, command: str) -> bool:
        """
        Send a command to Lightroom synchronously.

        Args:
            command: The command string to send

        Returns:
            True if send succeeded, False otherwise
        """
        with self._lock:
            if not self._connected:
                if not self.connect():
                    self._messages_failed += 1
                    return False

            try:
                self._socket.sendall(command.encode("utf-8"))
                self._messages_sent += 1
                return True

            except (BrokenPipeError, ConnectionResetError):
                self._handle_error("Connection lost to Lightroom")
                if self.reconnect():
                    # Retry once after reconnect
                    try:
                        self._socket.sendall(command.encode("utf-8"))
                        self._messages_sent += 1
                        return True
                    except OSError:
                        pass

                self._messages_failed += 1
                return False

            except socket.timeout:
                self._handle_error("Send timeout to Lightroom")
                self._messages_failed += 1
                return False

            except OSError as e:
                self._handle_error(f"Error sending to Lightroom: {e}")
                self._cleanup_socket()
                self._messages_failed += 1
                return False

    def send_async(self, command: str) -> bool:
        """
        Queue a command for asynchronous sending.

        This is preferred for high-frequency operations like slider movements.

        Args:
            command: The command string to send

        Returns:
            True if queued successfully, False if queue is full
        """
        try:
            self._message_queue.put_nowait(command)
            return True
        except queue.Full:
            self._handle_error("Message queue full, dropping command")
            return False

    def send_batch(self, commands: List[str]) -> int:
        """
        Send multiple commands in a batch.

        Args:
            commands: List of command strings to send

        Returns:
            Number of commands successfully sent
        """
        sent_count = 0
        with self._lock:
            if not self._connected:
                if not self.connect():
                    return 0

            # Combine commands for efficient sending
            batch_data = "\n".join(commands).encode("utf-8")

            try:
                self._socket.sendall(batch_data)
                sent_count = len(commands)
                self._messages_sent += sent_count

            except (BrokenPipeError, ConnectionResetError, socket.timeout, OSError) as e:
                self._handle_error(f"Batch send failed: {e}")
                self._cleanup_socket()

        return sent_count

    # =========================================================================
    # WORKER THREAD
    # =========================================================================

    def start_worker(self):
        """Start the background worker thread for async message sending."""
        if self._worker_thread and self._worker_thread.is_alive():
            return

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="LightroomSocketWorker"
        )
        self._worker_thread.start()
        print("Lightroom socket worker started")

    def stop_worker(self):
        """Stop the background worker thread."""
        self._stop_event.set()
        if self._worker_thread:
            # Put a sentinel to unblock the queue
            try:
                self._message_queue.put_nowait(None)
            except queue.Full:
                pass
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None
        print("Lightroom socket worker stopped")

    def _worker_loop(self):
        """Background worker loop for processing queued messages."""
        batch_size = 10
        batch_timeout = 0.01  # 10ms batching window

        while not self._stop_event.is_set():
            try:
                # Collect batch of messages
                batch = []
                try:
                    # Wait for first message
                    msg = self._message_queue.get(timeout=1.0)
                    if msg is None:  # Sentinel
                        continue
                    batch.append(msg)

                    # Try to get more messages without blocking
                    deadline = time.time() + batch_timeout
                    while len(batch) < batch_size and time.time() < deadline:
                        try:
                            msg = self._message_queue.get_nowait()
                            if msg is not None:
                                batch.append(msg)
                        except queue.Empty:
                            break

                except queue.Empty:
                    continue

                # Send batch
                if batch:
                    if len(batch) == 1:
                        self.send(batch[0])
                    else:
                        self.send_batch(batch)

            except Exception as e:
                self._handle_error(f"Worker error: {e}")
                time.sleep(0.1)

    # =========================================================================
    # CALLBACKS & ERROR HANDLING
    # =========================================================================

    def add_connect_callback(self, callback: Callable):
        """Register a callback for successful connections."""
        self._on_connect_callbacks.append(callback)

    def add_disconnect_callback(self, callback: Callable):
        """Register a callback for disconnections."""
        self._on_disconnect_callbacks.append(callback)

    def add_error_callback(self, callback: Callable[[str], None]):
        """Register a callback for errors."""
        self._on_error_callbacks.append(callback)

    def _notify_connect(self):
        """Notify all connect callbacks."""
        for cb in self._on_connect_callbacks:
            try:
                cb()
            except Exception as e:
                print(f"Error in connect callback: {e}")

    def _notify_disconnect(self):
        """Notify all disconnect callbacks."""
        for cb in self._on_disconnect_callbacks:
            try:
                cb()
            except Exception as e:
                print(f"Error in disconnect callback: {e}")

    def _handle_error(self, message: str):
        """Handle and report an error."""
        print(f"Lightroom socket error: {message}")
        for cb in self._on_error_callbacks:
            try:
                cb(message)
            except Exception as e:
                print(f"Error in error callback: {e}")

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> dict:
        """Get connection statistics."""
        with self._lock:
            return {
                "connected": self._connected,
                "messages_sent": self._messages_sent,
                "messages_failed": self._messages_failed,
                "reconnect_count": self._reconnect_count,
                "queue_size": self._message_queue.qsize(),
            }

    def reset_stats(self):
        """Reset statistics counters."""
        with self._lock:
            self._messages_sent = 0
            self._messages_failed = 0
            self._reconnect_count = 0


# Global singleton instance
_lightroom_socket: Optional[LightroomSocketManager] = None
_lightroom_socket_lock = threading.Lock()


def get_lightroom_socket() -> LightroomSocketManager:
    """Get the global Lightroom socket manager instance."""
    global _lightroom_socket
    with _lightroom_socket_lock:
        if _lightroom_socket is None:
            _lightroom_socket = LightroomSocketManager()
        return _lightroom_socket


def send_to_lightroom(command: str) -> bool:
    """
    Convenience function to send a command to Lightroom.

    Uses the global socket manager with automatic connection handling.

    Args:
        command: The command string to send

    Returns:
        True if send succeeded, False otherwise
    """
    return get_lightroom_socket().send(command)


def send_to_lightroom_async(command: str) -> bool:
    """
    Convenience function to queue a command for async sending.

    Args:
        command: The command string to send

    Returns:
        True if queued successfully, False if queue is full
    """
    socket_mgr = get_lightroom_socket()
    socket_mgr.start_worker()  # Ensure worker is running
    return socket_mgr.send_async(command)
