"""
tests/test_exporter.py
Unit tests for the Exporter class.
"""

import csv
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models.spt_test import Blow, SPTInterval, SPTTest
from src.storage.exporter import Exporter
from datetime import datetime, timezone


# ── Fixture ────────────────────────────────────────────────────────────────────

def make_test(test_id: str = "T001") -> SPTTest:
    t = SPTTest(
        test_id=test_id,
        borehole_id="BH-1",
        test_depth_m=3.0,
        date=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        location="Export Site",
        operator="Exporter",
    )
    for idx, (start, end, n) in enumerate(
        [(0.0, 150.0, 3), (150.0, 300.0, 7), (300.0, 450.0, 8)]
    ):
        iv = SPTInterval(interval_index=idx, start_depth_mm=start, end_depth_mm=end)
        for i in range(1, n + 1):
            iv.blows.append(
                Blow(i, datetime(2024, 6, 1, 12, idx, i, tzinfo=timezone.utc),
                     start + i * 10.0, 7.0)
            )
        t.intervals.append(iv)
    return t


# ── JSON export tests ──────────────────────────────────────────────────────────

class TestJsonExport:
    def test_single_test_json(self, tmp_path):
        path = str(tmp_path / "test.json")
        t = make_test()
        Exporter.to_json(t, path)
        assert os.path.exists(path)
        data = json.loads(open(path).read())
        assert data["test_id"] == "T001"

    def test_json_has_intervals(self, tmp_path):
        path = str(tmp_path / "t.json")
        Exporter.to_json(make_test(), path)
        data = json.loads(open(path).read())
        assert len(data["intervals"]) == 3

    def test_json_has_blows(self, tmp_path):
        path = str(tmp_path / "t2.json")
        Exporter.to_json(make_test(), path)
        data = json.loads(open(path).read())
        total_blows = sum(len(iv["blows"]) for iv in data["intervals"])
        assert total_blows == 18   # 3+7+8

    def test_multiple_tests_json(self, tmp_path):
        path = str(tmp_path / "multi.json")
        tests = [make_test("T1"), make_test("T2"), make_test("T3")]
        Exporter.tests_to_json(tests, path)
        data = json.loads(open(path).read())
        assert isinstance(data, list)
        assert len(data) == 3
        assert {d["test_id"] for d in data} == {"T1", "T2", "T3"}


# ── CSV export tests ───────────────────────────────────────────────────────────

class TestCsvExport:
    def test_summary_csv_created(self, tmp_path):
        path = str(tmp_path / "summary.csv")
        Exporter.to_csv_summary([make_test()], path)
        assert os.path.exists(path)

    def test_summary_csv_one_row_per_test(self, tmp_path):
        path = str(tmp_path / "s.csv")
        Exporter.to_csv_summary([make_test("A"), make_test("B")], path)
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 2
        ids = {r["test_id"] for r in rows}
        assert ids == {"A", "B"}

    def test_summary_csv_n_value(self, tmp_path):
        path = str(tmp_path / "nv.csv")
        t = make_test("T-NV")
        Exporter.to_csv_summary([t], path)
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert rows[0]["n_value"] == str(t.n_value())

    def test_blows_csv_created(self, tmp_path):
        path = str(tmp_path / "blows.csv")
        Exporter.to_csv_blows(make_test(), path)
        assert os.path.exists(path)

    def test_blows_csv_row_count(self, tmp_path):
        path = str(tmp_path / "blows2.csv")
        t = make_test()
        Exporter.to_csv_blows(t, path)
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == t.total_blows()

    def test_blows_csv_fields(self, tmp_path):
        path = str(tmp_path / "blows3.csv")
        Exporter.to_csv_blows(make_test(), path)
        with open(path, newline="") as fh:
            reader = csv.DictReader(fh)
            required_fields = {"test_id", "borehole_id", "interval_index",
                               "blow_number", "timestamp", "depth_mm", "impact_g"}
            assert required_fields <= set(reader.fieldnames)

    def test_intervals_csv(self, tmp_path):
        path = str(tmp_path / "intervals.csv")
        t = make_test()
        Exporter.to_csv_intervals(t, path)
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == len(t.intervals)

    def test_intervals_csv_blow_count(self, tmp_path):
        path = str(tmp_path / "int2.csv")
        t = make_test()
        Exporter.to_csv_intervals(t, path)
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        # First row is seating interval with 3 blows
        assert rows[0]["blow_count"] == "3"
