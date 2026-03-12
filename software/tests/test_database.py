"""
tests/test_database.py
Unit tests for the SQLite Database class.
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.storage.database import Database
from src.models.spt_test import Blow, SPTInterval, SPTTest


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    """Provide a fresh in-memory-equivalent (tmp file) Database."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    database.open()
    yield database
    database.close()


def make_test(test_id: str = "T001", n_drive1: int = 8,
              n_drive2: int = 10) -> SPTTest:
    t = SPTTest(
        test_id=test_id,
        borehole_id="BH-1",
        test_depth_m=3.0,
        date=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        location="Test Site",
        operator="Tester",
    )
    # Seating interval
    iv0 = SPTInterval(interval_index=0, start_depth_mm=0.0, end_depth_mm=150.0)
    for i in range(1, 4):
        iv0.blows.append(Blow(i, datetime.now(timezone.utc), i * 50.0, 6.0))
    t.intervals.append(iv0)

    # Drive interval 1
    iv1 = SPTInterval(interval_index=1, start_depth_mm=150.0, end_depth_mm=300.0,
                      hammer_efficiency=0.60)
    for i in range(1, n_drive1 + 1):
        iv1.blows.append(Blow(i + 3, datetime.now(timezone.utc),
                              150.0 + i * 18.75, 7.5))
    t.intervals.append(iv1)

    # Drive interval 2
    iv2 = SPTInterval(interval_index=2, start_depth_mm=300.0, end_depth_mm=450.0,
                      hammer_efficiency=0.60)
    for i in range(1, n_drive2 + 1):
        iv2.blows.append(Blow(i + 3 + n_drive1, datetime.now(timezone.utc),
                              300.0 + i * 15.0, 8.0))
    t.intervals.append(iv2)
    return t


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestDatabaseCRUD:
    def test_save_and_load_test(self, db):
        t = make_test("T001")
        db.save_test(t)
        loaded = db.load_test("T001")
        assert loaded is not None
        assert loaded.test_id == "T001"
        assert loaded.borehole_id == "BH-1"

    def test_load_nonexistent_returns_none(self, db):
        assert db.load_test("NONEXISTENT") is None

    def test_n_value_preserved(self, db):
        t = make_test("T002", n_drive1=7, n_drive2=9)
        db.save_test(t)
        loaded = db.load_test("T002")
        assert loaded.n_value() == 16

    def test_intervals_loaded(self, db):
        t = make_test("T003")
        db.save_test(t)
        loaded = db.load_test("T003")
        assert len(loaded.intervals) == 3

    def test_blows_loaded(self, db):
        t = make_test("T004", n_drive1=5, n_drive2=6)
        db.save_test(t)
        loaded = db.load_test("T004")
        drive1 = next(iv for iv in loaded.intervals if iv.interval_index == 1)
        assert drive1.blow_count() == 5

    def test_list_tests(self, db):
        db.save_test(make_test("T-A"))
        db.save_test(make_test("T-B"))
        db.save_test(make_test("T-C"))
        tests = db.list_tests()
        ids = {t.test_id for t in tests}
        assert {"T-A", "T-B", "T-C"} <= ids

    def test_delete_test(self, db):
        db.save_test(make_test("T-DEL"))
        db.delete_test("T-DEL")
        assert db.load_test("T-DEL") is None

    def test_save_replaces_existing(self, db):
        t = make_test("T-REPLACE", n_drive1=5, n_drive2=5)
        db.save_test(t)
        t2 = make_test("T-REPLACE", n_drive1=9, n_drive2=9)
        db.save_test(t2)
        loaded = db.load_test("T-REPLACE")
        assert loaded.n_value() == 18   # updated value

    def test_metadata_preserved(self, db):
        t = make_test("T-META")
        t.location = "My Location"
        t.operator = "Jane"
        db.save_test(t)
        loaded = db.load_test("T-META")
        assert loaded.location == "My Location"
        assert loaded.operator == "Jane"

    def test_context_manager(self, tmp_path):
        db_path = str(tmp_path / "ctx.db")
        with Database(db_path) as db:
            db.save_test(make_test("T-CTX"))
            assert db.load_test("T-CTX") is not None


class TestDatabaseNotOpen:
    def test_save_without_open_raises(self, tmp_path):
        db = Database(str(tmp_path / "closed.db"))
        with pytest.raises(RuntimeError):
            db.save_test(make_test())

    def test_load_without_open_raises(self, tmp_path):
        db = Database(str(tmp_path / "closed2.db"))
        with pytest.raises(RuntimeError):
            db.load_test("T001")
