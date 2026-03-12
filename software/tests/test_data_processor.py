"""
tests/test_data_processor.py
Unit tests for DataProcessor.
"""

import json
import pytest
from datetime import datetime, timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.acquisition.data_processor import DataProcessor
from src.models.spt_test import Blow


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_blow_msg(blow_number: int, depth_mm: float = 100.0,
                  impact_g: float = 7.0, ts: int = 1700000000) -> str:
    return json.dumps({
        "type": "blow",
        "ts": ts + blow_number,
        "blow": blow_number,
        "depth_mm": depth_mm,
        "impact_g": impact_g,
    })


def make_depth_msg(depth_mm: float, ts: int = 1700000000) -> str:
    return json.dumps({"type": "depth", "ts": ts, "depth_mm": depth_mm})


def make_status_msg(battery_pct: int = 80, ts: int = 1700000000) -> str:
    return json.dumps({"type": "status", "ts": ts, "battery_pct": battery_pct})


def _setup_processor(**kw):
    p = DataProcessor(**kw)
    p.start_test(
        test_id="T-TEST",
        borehole_id="BH-1",
        test_depth_m=3.0,
        location="Unit Test",
    )
    return p


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestDataProcessorBasics:
    def test_blow_callback_called(self):
        received = []
        p = _setup_processor(on_blow=received.append)
        p.start_interval(0, 0.0)
        p.process_line(make_blow_msg(1, 100.0))
        assert len(received) == 1
        assert isinstance(received[0], Blow)

    def test_blow_number_stored(self):
        received = []
        p = _setup_processor(on_blow=received.append)
        p.start_interval(0, 0.0)
        p.process_line(make_blow_msg(7, 200.0))
        assert received[0].blow_number == 7

    def test_depth_updated_on_blow(self):
        p = _setup_processor()
        p.start_interval(0, 0.0)
        p.process_line(make_blow_msg(1, 275.0))
        assert abs(p.last_depth_mm - 275.0) < 0.01

    def test_depth_message_updates_state(self):
        depths = []
        p = _setup_processor(on_depth=depths.append)
        p.process_line(make_depth_msg(350.5))
        assert abs(p.last_depth_mm - 350.5) < 0.01
        assert abs(depths[-1] - 350.5) < 0.01

    def test_status_callback(self):
        statuses = []
        p = _setup_processor(on_status=statuses.append)
        p.process_line(make_status_msg(75))
        assert len(statuses) == 1
        assert statuses[0]["battery_pct"] == 75

    def test_non_json_line_ignored(self):
        """Non-JSON input should not raise an exception."""
        p = _setup_processor()
        p.process_line("this is not json")   # should not raise

    def test_empty_line_ignored(self):
        p = _setup_processor()
        p.process_line("")   # should not raise

    def test_unknown_type_ignored(self):
        p = _setup_processor()
        p.process_line(json.dumps({"type": "foo", "data": 42}))  # no raise


class TestDataProcessorIntervals:
    def test_current_blow_count(self):
        p = _setup_processor()
        p.start_interval(0, 0.0)
        assert p.current_blow_count == 0
        p.process_line(make_blow_msg(1, 50.0))
        p.process_line(make_blow_msg(2, 100.0))
        assert p.current_blow_count == 2

    def test_interval_resets_on_new_interval(self):
        p = _setup_processor()
        p.start_interval(0, 0.0)
        for i in range(1, 6):
            p.process_line(make_blow_msg(i, i * 30.0))
        p.start_interval(1, 150.0)
        assert p.current_blow_count == 0

    def test_blows_accumulated_in_interval(self):
        p = _setup_processor()
        p.start_interval(1, 150.0)
        for i in range(1, 9):
            p.process_line(make_blow_msg(i, 150.0 + i * 18.75))
        assert p.current_blow_count == 8

    def test_finish_test_returns_test(self):
        p = _setup_processor()
        p.start_interval(0, 0.0)
        for i in range(1, 4):
            p.process_line(make_blow_msg(i, i * 50.0))
        p.start_interval(1, 150.0)
        for i in range(4, 12):
            p.process_line(make_blow_msg(i, 150.0 + (i - 3) * 18.75))
        p.start_interval(2, 300.0)
        for i in range(12, 22):
            p.process_line(make_blow_msg(i, 300.0 + (i - 11) * 15.0))
        test = p.finish_test()
        assert test is not None
        assert test.test_id == "T-TEST"
        assert test.n_value() == 18   # 8 + 10

    def test_finish_without_intervals(self):
        p = _setup_processor()
        test = p.finish_test()
        # Test with no intervals should still return a test object
        assert test is not None
        assert test.n_value() is None

    def test_start_interval_without_test_raises(self):
        p = DataProcessor()
        with pytest.raises(RuntimeError):
            p.start_interval(0, 0.0)

    def test_multiple_tests_independent(self):
        """Starting a second test should reset state fully."""
        p = DataProcessor()
        p.start_test("T1", "BH-1", 1.0)
        p.start_interval(0, 0.0)
        p.process_line(make_blow_msg(1, 50.0))
        p.start_test("T2", "BH-2", 2.0)
        p.start_interval(0, 0.0)
        assert p.current_blow_count == 0


class TestDataProcessorN60:
    def test_custom_hammer_efficiency(self):
        p = _setup_processor()
        p.start_interval(1, 150.0, hammer_efficiency=0.72)
        for i in range(1, 11):
            p.process_line(make_blow_msg(i, 150.0 + i * 15.0))
        p.start_interval(2, 300.0, hammer_efficiency=0.72)
        for i in range(11, 21):
            p.process_line(make_blow_msg(i, 300.0 + (i - 10) * 15.0))
        test = p.finish_test()
        assert test is not None
        # N60 = 20 * (0.72 / 0.60) = 24
        assert abs(test.n60() - 24.0) < 0.2
