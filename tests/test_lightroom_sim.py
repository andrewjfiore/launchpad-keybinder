#!/usr/bin/env python3
"""
Integration tests for the Lightroom simulator.

Tests end-to-end connectivity between the Launchpad mapper's socket client
and the simulated Lightroom server.
"""

import socket
import threading
import time

import pytest

from lightroom_sim import LightroomSimServer, LightroomState


# =============================================================================
# LightroomState unit tests
# =============================================================================

class TestLightroomState:
    """Tests for simulated Lightroom state."""

    def test_initial_params(self):
        state = LightroomState()
        assert state.params["exposure"] == 0.0
        assert state.params["contrast"] == 0
        assert state.params["temperature"] == 6500

    def test_process_slider_command(self):
        state = LightroomState()
        state.process_command("set_exposure:1.5")
        assert state.params["exposure"] == 1.5
        assert state.total_commands == 1

    def test_process_slider_negative(self):
        state = LightroomState()
        state.process_command("set_contrast:-50")
        assert state.params["contrast"] == -50.0

    def test_process_button_command(self):
        state = LightroomState()
        state.process_command("1")
        assert state.total_commands == 1
        assert state.command_log[-1]["type"] == "button"

    def test_process_numeric_command(self):
        state = LightroomState()
        state.process_command("57")
        assert state.command_log[-1]["detail"] == "Command ID: 57"

    def test_multiple_slider_updates(self):
        state = LightroomState()
        state.process_command("set_exposure:0.5")
        state.process_command("set_exposure:1.0")
        state.process_command("set_exposure:1.5")
        assert state.params["exposure"] == 1.5
        assert state.total_commands == 3

    def test_empty_command_ignored(self):
        state = LightroomState()
        state.process_command("")
        assert state.total_commands == 0

    def test_reset(self):
        state = LightroomState()
        state.process_command("set_exposure:2.0")
        state.reset()
        assert state.params["exposure"] == 0.0
        assert state.total_commands == 0

    def test_command_log_capped(self):
        state = LightroomState()
        for i in range(250):
            state.process_command(f"set_exposure:{i}")
        assert len(state.command_log) <= 200

    def test_snapshot(self):
        state = LightroomState()
        state.process_command("set_vibrance:30")
        snap = state.get_snapshot()
        assert snap["params"]["vibrance"] == 30
        assert snap["total_commands"] == 1
        assert len(snap["recent_log"]) == 1

    def test_new_param_created(self):
        """Unknown params get stored too."""
        state = LightroomState()
        state.process_command("set_dehaze:25")
        assert state.params["dehaze"] == 25.0

    def test_invalid_slider_value(self):
        state = LightroomState()
        state.process_command("set_exposure:abc")
        assert state.command_log[-1]["type"] == "slider_error"
        assert state.params["exposure"] == 0.0  # unchanged


# =============================================================================
# LightroomSimServer integration tests
# =============================================================================

class TestLightroomSimServer:
    """Integration tests for the simulator server."""

    @pytest.fixture
    def server(self):
        """Start a sim server on a random high port."""
        srv = LightroomSimServer(host="127.0.0.1", port=0)
        # Bind manually to get assigned port
        srv._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv._server_socket.settimeout(1.0)
        srv._server_socket.bind(("127.0.0.1", 0))
        srv.port = srv._server_socket.getsockname()[1]
        srv._server_socket.listen(5)
        srv._running = True
        t = threading.Thread(target=srv._accept_loop, daemon=True)
        t.start()
        yield srv
        srv.stop()

    def _connect(self, server):
        """Helper to connect a client socket."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(("127.0.0.1", server.port))
        return s

    def test_server_accepts_connection(self, server):
        client = self._connect(server)
        time.sleep(0.1)
        assert server.state.connected_clients == 1
        client.close()

    def test_server_receives_command(self, server):
        client = self._connect(server)
        client.sendall(b"set_exposure:2.0\n")
        time.sleep(0.2)
        assert server.state.params["exposure"] == 2.0
        client.close()

    def test_server_multiple_commands(self, server):
        client = self._connect(server)
        client.sendall(b"set_exposure:1.0\nset_contrast:50\n42\n")
        time.sleep(0.2)
        assert server.state.params["exposure"] == 1.0
        assert server.state.params["contrast"] == 50.0
        assert server.state.total_commands == 3
        client.close()

    def test_server_multiple_clients(self, server):
        c1 = self._connect(server)
        c2 = self._connect(server)
        time.sleep(0.1)
        assert server.state.connected_clients == 2
        c1.close()
        time.sleep(0.2)
        assert server.state.connected_clients == 1
        c2.close()

    def test_server_send_to_clients(self, server):
        """Test bidirectional: sim → mapper direction."""
        client = self._connect(server)
        time.sleep(0.1)
        server.send_to_clients("ping")
        data = client.recv(1024).decode("utf-8")
        assert "ping" in data
        client.close()

    def test_client_disconnect_cleanup(self, server):
        client = self._connect(server)
        time.sleep(0.1)
        assert server.state.connected_clients == 1
        client.close()
        time.sleep(0.3)
        assert server.state.connected_clients == 0

    def test_rapid_slider_updates(self, server):
        """Simulate rapid fader movement."""
        client = self._connect(server)
        for i in range(100):
            val = i / 100.0 * 5.0 - 2.5
            client.sendall(f"set_exposure:{val:.2f}\n".encode())
        time.sleep(0.5)
        assert server.state.total_commands == 100
        # Last value should be close to 2.45
        assert abs(server.state.params["exposure"] - 2.45) < 0.1
        client.close()

    def test_events_generated(self, server):
        client = self._connect(server)
        client.sendall(b"set_exposure:1.0\n")
        time.sleep(0.2)
        events = server.get_events()
        event_types = [e[0] for e in events]
        assert "connect" in event_types
        assert "command" in event_types
        client.close()


# =============================================================================
# Integration with LightroomSocketManager
# =============================================================================

class TestMapperToSimIntegration:
    """
    End-to-end test: LightroomSocketManager → LightroomSimServer.
    Verifies the mapper can talk to the simulator exactly as it would
    talk to real Lightroom.
    """

    @pytest.fixture
    def sim_and_manager(self):
        from lightroom_socket import LightroomSocketManager

        srv = LightroomSimServer(host="127.0.0.1", port=0)
        srv._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv._server_socket.settimeout(1.0)
        srv._server_socket.bind(("127.0.0.1", 0))
        srv.port = srv._server_socket.getsockname()[1]
        srv._server_socket.listen(5)
        srv._running = True
        t = threading.Thread(target=srv._accept_loop, daemon=True)
        t.start()

        mgr = LightroomSocketManager(
            host="127.0.0.1",
            port=srv.port,
            connect_timeout=2.0,
            send_timeout=1.0,
        )
        yield srv, mgr
        mgr.stop_worker()
        mgr.disconnect()
        srv.stop()

    def test_manager_connects_to_sim(self, sim_and_manager):
        srv, mgr = sim_and_manager
        assert mgr.connect() is True
        assert mgr.is_connected
        time.sleep(0.1)
        assert srv.state.connected_clients == 1

    def test_manager_sends_command(self, sim_and_manager):
        srv, mgr = sim_and_manager
        mgr.connect()
        result = mgr.send("set_exposure:3.0")
        assert result is True
        time.sleep(0.2)
        assert srv.state.params["exposure"] == 3.0

    def test_manager_sends_button(self, sim_and_manager):
        srv, mgr = sim_and_manager
        mgr.connect()
        mgr.send("42")
        time.sleep(0.2)
        assert srv.state.total_commands == 1
        assert srv.state.command_log[-1]["type"] == "button"

    def test_manager_batch_send(self, sim_and_manager):
        srv, mgr = sim_and_manager
        mgr.connect()
        commands = ["set_exposure:1.0", "set_contrast:25", "set_vibrance:50"]
        count = mgr.send_batch(commands)
        assert count == 3
        time.sleep(0.3)
        assert srv.state.params["exposure"] == 1.0
        assert srv.state.params["contrast"] == 25.0
        assert srv.state.params["vibrance"] == 50.0

    def test_manager_reconnect(self, sim_and_manager):
        srv, mgr = sim_and_manager
        mgr.connect()
        assert mgr.is_connected
        mgr.disconnect()
        assert not mgr.is_connected
        assert mgr.reconnect() is True
        assert mgr.is_connected

    def test_manager_async_send(self, sim_and_manager):
        srv, mgr = sim_and_manager
        mgr.connect()
        mgr.start_worker()
        mgr.send_async("set_shadows:40")
        time.sleep(0.5)
        assert srv.state.params["shadows"] == 40.0

    def test_manager_stats_after_sends(self, sim_and_manager):
        srv, mgr = sim_and_manager
        mgr.connect()
        mgr.send("set_exposure:1.0")
        mgr.send("set_contrast:10")
        stats = mgr.get_stats()
        assert stats["messages_sent"] >= 2
        assert stats["connected"] is True

    def test_bidirectional_communication(self, sim_and_manager):
        """Verify sim can send data back to the mapper's socket."""
        srv, mgr = sim_and_manager
        mgr.connect()
        time.sleep(0.1)
        # Send from sim to mapper
        srv.send_to_clients("status:ok")
        # The mapper socket should receive it (we read directly)
        mgr._socket.settimeout(2.0)
        data = mgr._socket.recv(1024).decode("utf-8")
        assert "status:ok" in data
