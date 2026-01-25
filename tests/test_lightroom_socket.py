#!/usr/bin/env python3
"""Tests for the lightroom_socket module."""

import socket
import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from lightroom_socket import (
    LightroomSocketManager,
    SliderThrottler,
    get_lightroom_socket,
    send_to_lightroom,
    send_slider_to_lightroom,
)


class TestLightroomSocketManager:
    """Tests for LightroomSocketManager class."""

    def test_initialization(self):
        """Test manager initializes with correct defaults."""
        manager = LightroomSocketManager()
        assert manager.host == "127.0.0.1"
        assert manager.port == 55555
        assert manager.connect_timeout == 2.0
        assert manager.send_timeout == 0.5
        assert not manager.is_connected

    def test_initialization_custom_values(self):
        """Test manager initializes with custom values."""
        manager = LightroomSocketManager(
            host="192.168.1.1",
            port=12345,
            connect_timeout=5.0,
            send_timeout=1.0
        )
        assert manager.host == "192.168.1.1"
        assert manager.port == 12345

    def test_connect_refused(self):
        """Test connection when server not running."""
        manager = LightroomSocketManager(host="127.0.0.1", port=65432)
        result = manager.connect()
        assert result is False
        assert not manager.is_connected

    def test_disconnect_when_not_connected(self):
        """Test disconnect when not connected."""
        manager = LightroomSocketManager()
        # Should not raise
        manager.disconnect()
        assert not manager.is_connected

    def test_send_when_not_connected(self):
        """Test send attempts connection first."""
        manager = LightroomSocketManager(host="127.0.0.1", port=65432)
        result = manager.send("test")
        assert result is False

    def test_send_async_queue(self):
        """Test async send queues message."""
        manager = LightroomSocketManager()
        result = manager.send_async("test_command")
        assert result is True
        assert manager._message_queue.qsize() == 1

    def test_send_async_queue_full(self):
        """Test async send when queue is full."""
        manager = LightroomSocketManager()
        # Fill the queue
        for _ in range(1000):
            manager._message_queue.put_nowait("dummy")

        result = manager.send_async("overflow")
        assert result is False

    def test_get_stats(self):
        """Test statistics retrieval."""
        manager = LightroomSocketManager()
        stats = manager.get_stats()
        assert 'connected' in stats
        assert 'messages_sent' in stats
        assert 'messages_failed' in stats
        assert 'reconnect_count' in stats
        assert 'queue_size' in stats

    def test_reset_stats(self):
        """Test statistics reset."""
        manager = LightroomSocketManager()
        manager._messages_sent = 10
        manager._messages_failed = 5
        manager._reconnect_count = 2

        manager.reset_stats()

        assert manager._messages_sent == 0
        assert manager._messages_failed == 0
        assert manager._reconnect_count == 0

    def test_callbacks_registration(self):
        """Test callback registration."""
        manager = LightroomSocketManager()

        connect_called = []
        disconnect_called = []
        error_called = []

        manager.add_connect_callback(lambda: connect_called.append(True))
        manager.add_disconnect_callback(lambda: disconnect_called.append(True))
        manager.add_error_callback(lambda msg: error_called.append(msg))

        manager._notify_connect()
        manager._notify_disconnect()
        manager._handle_error("test error")

        assert len(connect_called) == 1
        assert len(disconnect_called) == 1
        assert len(error_called) == 1
        assert error_called[0] == "test error"

    def test_worker_start_stop(self):
        """Test worker thread start and stop."""
        manager = LightroomSocketManager()

        manager.start_worker()
        assert manager._worker_thread is not None
        assert manager._worker_thread.is_alive()

        manager.stop_worker()
        assert not manager._stop_event.is_set() or manager._worker_thread is None


class TestMockConnection:
    """Tests using mocked socket connections."""

    def test_send_with_mocked_socket(self):
        """Test sending with a mocked socket."""
        manager = LightroomSocketManager()

        # Create a mock socket
        mock_socket = MagicMock()
        manager._socket = mock_socket
        manager._connected = True

        result = manager.send("test_command")
        assert result is True
        # send() adds newline if missing; Lightroom plugin splits on newlines
        mock_socket.sendall.assert_called_once_with(b"test_command\n")
        assert manager._messages_sent == 1

    def test_send_broken_pipe_reconnects(self):
        """Test that broken pipe triggers reconnect."""
        manager = LightroomSocketManager()

        # Setup initial connection
        mock_socket = MagicMock()
        mock_socket.sendall.side_effect = BrokenPipeError()
        manager._socket = mock_socket
        manager._connected = True

        # This should fail (no real server to reconnect to)
        result = manager.send("test")
        assert result is False
        assert manager._messages_failed == 1

    def test_send_batch(self):
        """Test batch sending."""
        manager = LightroomSocketManager()

        mock_socket = MagicMock()
        manager._socket = mock_socket
        manager._connected = True

        commands = ["cmd1", "cmd2", "cmd3"]
        count = manager.send_batch(commands)

        assert count == 3
        # Should be called once with combined data; each command gets newline
        assert mock_socket.sendall.call_count == 1
        call_data = mock_socket.sendall.call_args[0][0]
        assert call_data == b"cmd1\ncmd2\ncmd3\n"


class TestSliderThrottler:
    """Tests for SliderThrottler class."""

    def test_initialization(self):
        """Test throttler initializes with correct defaults."""
        throttler = SliderThrottler()
        assert throttler.min_interval_ms == 16.0
        assert throttler.debounce_ms == 50.0

    def test_first_update_sends_immediately(self):
        """Test first update for a slider is sent immediately."""
        sent_commands = []
        throttler = SliderThrottler(
            min_interval_ms=100,
            debounce_ms=50,
            send_func=lambda cmd: sent_commands.append(cmd)
        )

        result = throttler.update("Exposure", "slider_move:Exposure:+0.1")
        assert result is True

        # Give a tiny bit of time for the send
        time.sleep(0.01)
        assert len(sent_commands) == 1
        assert sent_commands[0] == "slider_move:Exposure:+0.1"

    def test_rapid_updates_are_throttled(self):
        """Test rapid updates are throttled and only final value sent."""
        sent_commands = []
        throttler = SliderThrottler(
            min_interval_ms=100,  # 100ms between sends
            debounce_ms=50,
            send_func=lambda cmd: sent_commands.append(cmd)
        )

        # Send first (immediate)
        throttler.update("Exposure", "slider_move:Exposure:+0.1")

        # Rapid updates within throttle window
        for i in range(10):
            throttler.update("Exposure", f"slider_move:Exposure:+0.{i+2}")

        # Should have sent first one immediately
        assert len(sent_commands) >= 1

        # Wait for debounce
        time.sleep(0.2)

        # Should have sent final value
        assert sent_commands[-1] == "slider_move:Exposure:+0.11"

    def test_different_sliders_tracked_independently(self):
        """Test different sliders are throttled independently."""
        sent_commands = []
        throttler = SliderThrottler(
            min_interval_ms=100,
            debounce_ms=50,
            send_func=lambda cmd: sent_commands.append(cmd)
        )

        # First update for each slider should send immediately
        throttler.update("Exposure", "slider_move:Exposure:+0.1")
        throttler.update("Contrast", "slider_move:Contrast:+0.2")

        time.sleep(0.01)
        assert len(sent_commands) == 2

    def test_flush_sends_pending(self):
        """Test flush sends all pending values immediately."""
        sent_commands = []
        throttler = SliderThrottler(
            min_interval_ms=1000,  # Long interval
            debounce_ms=500,
            send_func=lambda cmd: sent_commands.append(cmd)
        )

        # First update sends immediately
        throttler.update("Exposure", "cmd1")
        time.sleep(0.01)
        initial_count = len(sent_commands)

        # Second update within throttle window
        throttler.update("Exposure", "cmd2")

        # Flush should send pending
        throttler.flush()
        time.sleep(0.01)

        assert len(sent_commands) > initial_count
        assert "cmd2" in sent_commands

    def test_clear_removes_pending(self):
        """Test clear removes all pending without sending."""
        sent_commands = []
        throttler = SliderThrottler(
            min_interval_ms=1000,
            debounce_ms=500,
            send_func=lambda cmd: sent_commands.append(cmd)
        )

        # First update
        throttler.update("Exposure", "cmd1")
        time.sleep(0.01)
        initial_count = len(sent_commands)

        # Queue another
        throttler.update("Exposure", "cmd2")

        # Clear without sending
        throttler.clear()
        time.sleep(0.1)

        # Should not have sent the second command
        assert len(sent_commands) == initial_count

    def test_get_stats(self):
        """Test statistics retrieval."""
        throttler = SliderThrottler()
        stats = throttler.get_stats()
        assert 'throttled_count' in stats
        assert 'sent_count' in stats
        assert 'pending_count' in stats
        assert 'active_timers' in stats


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_lightroom_socket_singleton(self):
        """Test that get_lightroom_socket returns singleton."""
        socket1 = get_lightroom_socket()
        socket2 = get_lightroom_socket()
        assert socket1 is socket2

    @patch.object(LightroomSocketManager, 'send')
    def test_send_to_lightroom(self, mock_send):
        """Test send_to_lightroom convenience function."""
        mock_send.return_value = True
        result = send_to_lightroom("test_command")
        assert result is True
