"""
tests/test_spt_models.py
Unit tests for the SPT data model classes:
  Blow, SPTInterval, SPTTest
"""

import json
import pytest
from datetime import datetime, timedelta, timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models.spt_test import Blow, SPTInterval, SPTTest


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_blow(number: int = 1, depth_mm: float = 100.0, impact_g: float = 7.5) -> Blow:
    base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    return Blow(
        blow_number=number,
        timestamp=base + timedelta(seconds=number * 3),
        depth_mm=depth_mm,
        impact_g=impact_g,
    )


def make_interval(index: int = 0, blows: int = 5,
                  start: float = 0.0, end: float = 150.0,
                  hammer_eff: float = 0.60) -> SPTInterval:
    iv = SPTInterval(
        interval_index=index,
        start_depth_mm=start,
        end_depth_mm=end,
        hammer_efficiency=hammer_eff,
    )
    for i in range(1, blows + 1):
        iv.blows.append(make_blow(i, start + i * (end - start) / blows))
    return iv


def make_test(n_seating: int = 3, n_drive1: int = 8, n_drive2: int = 10) -> SPTTest:
    test = SPTTest(
        test_id="T001",
        borehole_id="BH-1",
        test_depth_m=3.0,
        date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        location="Test Site",
        operator="Tester",
    )
    test.intervals.append(make_interval(0, n_seating, 0.0, 150.0))
    test.intervals.append(make_interval(1, n_drive1, 150.0, 300.0))
    test.intervals.append(make_interval(2, n_drive2, 300.0, 450.0))
    return test


# ── Blow tests ─────────────────────────────────────────────────────────────────

class TestBlow:
    def test_to_dict_fields(self):
        b = make_blow(3, 250.0, 9.1)
        d = b.to_dict()
        assert d["blow_number"] == 3
        assert d["depth_mm"] == 250.0
        assert d["impact_g"] == 9.1
        assert "timestamp" in d

    def test_round_trip(self):
        b = make_blow(5, 300.5, 8.33)
        b2 = Blow.from_dict(b.to_dict())
        assert b2.blow_number == b.blow_number
        assert abs(b2.depth_mm - b.depth_mm) < 0.01
        assert abs(b2.impact_g - b.impact_g) < 0.01

    def test_depth_precision(self):
        b = make_blow(1, 123.456789)
        d = b.to_dict()
        # to_dict rounds to 1 decimal
        assert d["depth_mm"] == round(123.456789, 1)


# ── SPTInterval tests ──────────────────────────────────────────────────────────

class TestSPTInterval:
    def test_blow_count(self):
        iv = make_interval(1, blows=7)
        assert iv.blow_count() == 7

    def test_n_value_equals_blow_count(self):
        iv = make_interval(1, blows=12)
        assert iv.n_value() == 12

    def test_n60_standard_efficiency(self):
        """With all corrections = 1.0 and Em = 0.60, N60 should equal N."""
        iv = make_interval(1, blows=10, hammer_eff=0.60)
        assert abs(iv.n60() - 10.0) < 0.05

    def test_n60_higher_efficiency(self):
        """With Em=0.72 (auto-hammer), N60 should be 20% higher than N."""
        iv = make_interval(1, blows=10, hammer_eff=0.72)
        expected = 10 * (0.72 / 0.60)
        assert abs(iv.n60() - expected) < 0.1

    def test_n60_lower_efficiency(self):
        """With Em=0.45 (rope-pulley), N60 should be 25% lower than N."""
        iv = make_interval(1, blows=20, hammer_eff=0.45)
        expected = 20 * (0.45 / 0.60)
        assert abs(iv.n60() - expected) < 0.1

    def test_penetration_mm(self):
        iv = make_interval(0, 5, 0.0, 150.0)
        assert abs(iv.penetration_mm() - 150.0) < 0.01

    def test_round_trip_serialisation(self):
        iv = make_interval(2, blows=9, start=300.0, end=450.0)
        iv2 = SPTInterval.from_dict(iv.to_dict())
        assert iv2.interval_index == 2
        assert iv2.blow_count() == 9
        assert abs(iv2.start_depth_mm - 300.0) < 0.01

    def test_empty_interval(self):
        iv = SPTInterval(interval_index=0, start_depth_mm=0.0, end_depth_mm=150.0)
        assert iv.blow_count() == 0
        assert iv.n_value() == 0
        assert iv.n60() == 0.0


# ── SPTTest tests ──────────────────────────────────────────────────────────────

class TestSPTTest:
    def test_n_value(self):
        test = make_test(n_seating=3, n_drive1=8, n_drive2=10)
        assert test.n_value() == 18   # sum of drive intervals 1+2

    def test_n_value_requires_two_drive_intervals(self):
        test = SPTTest(
            test_id="T-X", borehole_id="BH", test_depth_m=1.0,
            date=datetime.now(timezone.utc)
        )
        assert test.n_value() is None
        test.intervals.append(make_interval(0, 3))
        assert test.n_value() is None
        test.intervals.append(make_interval(1, 6))
        assert test.n_value() is None   # only one drive interval
        test.intervals.append(make_interval(2, 7))
        assert test.n_value() == 13

    def test_n60_standard(self):
        """With all corrections at default (Em=0.60), N60 == N."""
        test = make_test(n_seating=3, n_drive1=8, n_drive2=10)
        assert abs(test.n60() - 18.0) < 0.1

    def test_total_blows(self):
        test = make_test(3, 8, 10)
        assert test.total_blows() == 21   # 3+8+10

    def test_seating_excluded_from_n(self):
        """Verify seating interval blows are NOT counted in N-value."""
        test = make_test(n_seating=100, n_drive1=5, n_drive2=6)
        assert test.n_value() == 11

    def test_to_dict_structure(self):
        test = make_test()
        d = test.to_dict()
        assert "test_id" in d
        assert "intervals" in d
        assert isinstance(d["intervals"], list)
        assert len(d["intervals"]) == 3

    def test_json_round_trip(self):
        test = make_test(3, 7, 9)
        json_str = test.to_json()
        test2 = SPTTest.from_json(json_str)
        assert test2.test_id == test.test_id
        assert test2.borehole_id == test.borehole_id
        assert test2.n_value() == test.n_value()
        assert len(test2.intervals) == len(test.intervals)

    def test_from_json_preserves_blows(self):
        test = make_test(2, 5, 6)
        test2 = SPTTest.from_json(test.to_json())
        for i, iv in enumerate(test.intervals):
            assert test2.intervals[i].blow_count() == iv.blow_count()

    def test_operator_location_serialised(self):
        test = make_test()
        d = test.to_dict()
        assert d["location"] == "Test Site"
        assert d["operator"] == "Tester"
