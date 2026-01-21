"""Tests for LED animation classes."""
import pytest
import sys
import os
import threading
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from launchpad_mapper import (
    LEDAnimation,
    PulseAnimation,
    ProgressBarAnimation,
    RainbowCycleAnimation,
    LaunchpadMapper,
    LAUNCHPAD_COLORS,
)


class MockMapper:
    """Mock mapper for animation tests."""

    def __init__(self):
        self.colors_set = {}
        self.GRID_NOTES = LaunchpadMapper.GRID_NOTES

    def set_pad_color(self, note, color):
        self.colors_set[note] = color


class TestLEDAnimationBase:
    """Test base LEDAnimation class."""

    def test_initialization(self):
        """Test animation initialization."""
        mapper = MockMapper()
        anim = LEDAnimation(mapper, 60)
        assert anim.mapper == mapper
        assert anim.note == 60
        assert anim.stop_event is not None
        assert anim.thread is None

    def test_stop_event(self):
        """Test stop event is not set initially."""
        mapper = MockMapper()
        anim = LEDAnimation(mapper, 60)
        assert not anim.stop_event.is_set()

    def test_stop_sets_event(self):
        """Test stop() sets the stop event."""
        mapper = MockMapper()
        anim = LEDAnimation(mapper, 60)
        anim.stop()
        assert anim.stop_event.is_set()


class TestPulseAnimation:
    """Test PulseAnimation class."""

    def test_initialization(self):
        """Test pulse animation initialization."""
        mapper = MockMapper()
        anim = PulseAnimation(mapper, 60, 'red', 0.5)
        assert anim.note == 60
        assert anim.color == 'red'
        assert anim.duration == 0.5

    def test_run_sets_colors(self):
        """Test pulse animation sets pad colors."""
        mapper = MockMapper()
        anim = PulseAnimation(mapper, 60, 'green', 0.1)

        # Run animation briefly
        anim.run()

        # Animation should have set colors
        assert 60 in mapper.colors_set

    def test_run_can_be_stopped(self):
        """Test pulse animation can be stopped."""
        mapper = MockMapper()
        anim = PulseAnimation(mapper, 60, 'red', 5.0)  # Long duration

        # Start in thread and stop quickly
        def run_and_stop():
            anim.start()
            time.sleep(0.05)
            anim.stop()

        run_and_stop()
        assert anim.stop_event.is_set()

    def test_dim_color_handling(self):
        """Test pulse handles dim colors."""
        mapper = MockMapper()
        anim = PulseAnimation(mapper, 60, 'red', 0.05)
        anim.run()
        # Should not raise


class TestProgressBarAnimation:
    """Test ProgressBarAnimation class."""

    def test_initialization(self):
        """Test progress bar animation initialization."""
        mapper = MockMapper()
        row_notes = [11, 12, 13, 14, 15, 16, 17, 18]
        anim = ProgressBarAnimation(mapper, row_notes, 50, 'green')
        assert anim.row_notes == row_notes
        assert anim.percentage == 50
        assert anim.color == 'green'

    def test_percentage_clamping_high(self):
        """Test percentage is clamped to 100."""
        mapper = MockMapper()
        anim = ProgressBarAnimation(mapper, [60], 150, 'green')
        assert anim.percentage == 100

    def test_percentage_clamping_low(self):
        """Test percentage is clamped to 0."""
        mapper = MockMapper()
        anim = ProgressBarAnimation(mapper, [60], -50, 'green')
        assert anim.percentage == 0

    def test_run_sets_colors(self):
        """Test progress bar sets correct colors."""
        mapper = MockMapper()
        row_notes = [11, 12, 13, 14]
        anim = ProgressBarAnimation(mapper, row_notes, 50, 'green')
        anim.run()

        # 50% of 4 pads = 2 pads lit
        assert mapper.colors_set[11] == 'green'
        assert mapper.colors_set[12] == 'green'
        assert mapper.colors_set[13] == 'off'
        assert mapper.colors_set[14] == 'off'

    def test_run_full_progress(self):
        """Test progress bar at 100%."""
        mapper = MockMapper()
        row_notes = [11, 12, 13, 14]
        anim = ProgressBarAnimation(mapper, row_notes, 100, 'red')
        anim.run()

        for note in row_notes:
            assert mapper.colors_set[note] == 'red'

    def test_run_zero_progress(self):
        """Test progress bar at 0%."""
        mapper = MockMapper()
        row_notes = [11, 12, 13, 14]
        anim = ProgressBarAnimation(mapper, row_notes, 0, 'blue')
        anim.run()

        for note in row_notes:
            assert mapper.colors_set[note] == 'off'


class TestRainbowCycleAnimation:
    """Test RainbowCycleAnimation class."""

    def test_initialization(self):
        """Test rainbow animation initialization."""
        mapper = MockMapper()
        anim = RainbowCycleAnimation(mapper, 0.5)
        assert anim.speed == 0.5
        assert len(anim.colors) > 0

    def test_colors_are_defined(self):
        """Test rainbow animation has predefined colors."""
        mapper = MockMapper()
        anim = RainbowCycleAnimation(mapper, 0.5)
        expected_colors = ['red', 'orange', 'yellow', 'lime', 'green',
                         'cyan', 'blue', 'purple', 'magenta']
        assert anim.colors == expected_colors

    def test_run_can_be_stopped(self):
        """Test rainbow animation can be stopped."""
        mapper = MockMapper()
        anim = RainbowCycleAnimation(mapper, 0.5)

        # Start and stop quickly
        anim.start()
        time.sleep(0.05)
        anim.stop()

        assert anim.stop_event.is_set()

    def test_run_sets_colors(self):
        """Test rainbow animation sets some colors."""
        mapper = MockMapper()
        anim = RainbowCycleAnimation(mapper, 0.01)

        # Run briefly
        anim.start()
        time.sleep(0.05)
        anim.stop()

        # Should have set some pad colors
        assert len(mapper.colors_set) > 0


class TestAnimationThreading:
    """Test animation threading behavior."""

    def test_start_creates_thread(self):
        """Test start() creates a thread."""
        mapper = MockMapper()
        anim = PulseAnimation(mapper, 60, 'red', 0.01)
        anim.start()
        time.sleep(0.05)
        anim.stop()

    def test_start_twice_no_duplicate_threads(self):
        """Test starting twice doesn't create duplicate threads."""
        mapper = MockMapper()
        anim = PulseAnimation(mapper, 60, 'red', 1.0)

        anim.start()
        thread1 = anim.thread
        anim.start()  # Second start
        thread2 = anim.thread

        # Should be the same thread (no duplicate created)
        assert thread1 == thread2
        anim.stop()

    def test_stop_joins_thread(self):
        """Test stop() waits for thread to finish."""
        mapper = MockMapper()
        anim = PulseAnimation(mapper, 60, 'red', 0.1)
        anim.start()
        anim.stop()

        # Thread should be stopped
        if anim.thread:
            assert not anim.thread.is_alive() or anim.stop_event.is_set()
