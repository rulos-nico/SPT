"""
storage/database.py
SQLite database for persistent storage of SPT tests.

Schema
------
tests         – one row per SPTTest (header information + cached N-values)
intervals     – one row per SPTInterval, linked to a test
blows         – one row per Blow, linked to an interval
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models.spt_test import Blow, SPTInterval, SPTTest

logger = logging.getLogger(__name__)

# Current schema version – increment when schema changes
SCHEMA_VERSION = 1


class Database:
    """
    Manages the SQLite database for the SPT measurement system.

    Usage::

        db = Database("spt_data.db")
        db.open()
        db.save_test(test)
        tests = db.list_tests()
        db.close()
    """

    def __init__(self, path: str = "spt_data.db") -> None:
        self._path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None

    # ── Connection lifecycle ───────────────────────────────────────────────

    def open(self) -> None:
        """Open (or create) the database and ensure schema is up to date."""
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.row_factory = sqlite3.Row
        self._apply_schema()

    def close(self) -> None:
        """Commit pending changes and close the connection."""
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ── CRUD operations ────────────────────────────────────────────────────

    def save_test(self, test: SPTTest) -> None:
        """Insert or replace a complete test (test + intervals + blows)."""
        conn = self._require_conn()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tests
                    (test_id, borehole_id, test_depth_m, date, location,
                     operator, n_value, n60, total_blows)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    test.test_id,
                    test.borehole_id,
                    test.test_depth_m,
                    test.date.isoformat(),
                    test.location,
                    test.operator,
                    test.n_value(),
                    test.n60(),
                    test.total_blows(),
                ),
            )
            # Remove old intervals & blows for this test_id before re-inserting
            conn.execute(
                "DELETE FROM blows WHERE interval_id IN "
                "(SELECT id FROM intervals WHERE test_id=?)",
                (test.test_id,),
            )
            conn.execute(
                "DELETE FROM intervals WHERE test_id=?", (test.test_id,)
            )
            for iv in test.intervals:
                cursor = conn.execute(
                    """
                    INSERT INTO intervals
                        (test_id, interval_index, start_depth_mm,
                         end_depth_mm, start_time, end_time,
                         hammer_efficiency, borehole_correction,
                         sampler_correction, rod_length_correction,
                         blow_count, n60)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        test.test_id,
                        iv.interval_index,
                        iv.start_depth_mm,
                        iv.end_depth_mm,
                        iv.start_time.isoformat() if iv.start_time else None,
                        iv.end_time.isoformat() if iv.end_time else None,
                        iv.hammer_efficiency,
                        iv.borehole_correction,
                        iv.sampler_correction,
                        iv.rod_length_correction,
                        iv.blow_count(),
                        iv.n60(),
                    ),
                )
                iv_id = cursor.lastrowid
                for blow in iv.blows:
                    conn.execute(
                        """
                        INSERT INTO blows
                            (interval_id, blow_number, timestamp,
                             depth_mm, impact_g)
                        VALUES (?,?,?,?,?)
                        """,
                        (
                            iv_id,
                            blow.blow_number,
                            blow.timestamp.isoformat(),
                            blow.depth_mm,
                            blow.impact_g,
                        ),
                    )

    def load_test(self, test_id: str) -> Optional[SPTTest]:
        """Load a full test (with intervals and blows) by ID."""
        conn = self._require_conn()
        row = conn.execute(
            "SELECT * FROM tests WHERE test_id=?", (test_id,)
        ).fetchone()
        if row is None:
            return None
        return self._hydrate_test(conn, dict(row))

    def list_tests(self) -> List[SPTTest]:
        """Return all tests (without blow details for performance)."""
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT * FROM tests ORDER BY date DESC"
        ).fetchall()
        return [self._hydrate_test(conn, dict(r)) for r in rows]

    def delete_test(self, test_id: str) -> None:
        """Delete a test and all its intervals and blows."""
        conn = self._require_conn()
        with conn:
            conn.execute(
                "DELETE FROM blows WHERE interval_id IN "
                "(SELECT id FROM intervals WHERE test_id=?)",
                (test_id,),
            )
            conn.execute(
                "DELETE FROM intervals WHERE test_id=?", (test_id,)
            )
            conn.execute("DELETE FROM tests WHERE test_id=?", (test_id,))

    # ── Schema management ──────────────────────────────────────────────────

    def _apply_schema(self) -> None:
        conn = self._require_conn()
        with conn:
            conn.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                );
                INSERT OR IGNORE INTO schema_version VALUES ({SCHEMA_VERSION});

                CREATE TABLE IF NOT EXISTS tests (
                    test_id      TEXT PRIMARY KEY,
                    borehole_id  TEXT NOT NULL,
                    test_depth_m REAL NOT NULL,
                    date         TEXT NOT NULL,
                    location     TEXT DEFAULT '',
                    operator     TEXT DEFAULT '',
                    n_value      INTEGER,
                    n60          REAL,
                    total_blows  INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS intervals (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id              TEXT NOT NULL REFERENCES tests(test_id),
                    interval_index       INTEGER NOT NULL,
                    start_depth_mm       REAL NOT NULL,
                    end_depth_mm         REAL DEFAULT 0,
                    start_time           TEXT,
                    end_time             TEXT,
                    hammer_efficiency    REAL DEFAULT 0.60,
                    borehole_correction  REAL DEFAULT 1.00,
                    sampler_correction   REAL DEFAULT 1.00,
                    rod_length_correction REAL DEFAULT 1.00,
                    blow_count           INTEGER DEFAULT 0,
                    n60                  REAL
                );

                CREATE TABLE IF NOT EXISTS blows (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    interval_id INTEGER NOT NULL REFERENCES intervals(id),
                    blow_number INTEGER NOT NULL,
                    timestamp   TEXT NOT NULL,
                    depth_mm    REAL NOT NULL,
                    impact_g    REAL DEFAULT 0.0
                );
                """
            )

    # ── Private helpers ────────────────────────────────────────────────────

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not open. Call open() first.")
        return self._conn

    def _hydrate_test(self, conn: sqlite3.Connection, row: dict) -> SPTTest:
        test = SPTTest(
            test_id=row["test_id"],
            borehole_id=row["borehole_id"],
            test_depth_m=float(row["test_depth_m"]),
            date=datetime.fromisoformat(row["date"]),
            location=row.get("location", ""),
            operator=row.get("operator", ""),
        )
        iv_rows = conn.execute(
            "SELECT * FROM intervals WHERE test_id=? ORDER BY interval_index",
            (test.test_id,),
        ).fetchall()
        for iv_row in iv_rows:
            iv_dict = dict(iv_row)
            iv = SPTInterval(
                interval_index=iv_dict["interval_index"],
                start_depth_mm=float(iv_dict["start_depth_mm"]),
                end_depth_mm=float(iv_dict["end_depth_mm"]),
                start_time=(
                    datetime.fromisoformat(iv_dict["start_time"])
                    if iv_dict.get("start_time")
                    else None
                ),
                end_time=(
                    datetime.fromisoformat(iv_dict["end_time"])
                    if iv_dict.get("end_time")
                    else None
                ),
                hammer_efficiency=float(iv_dict.get("hammer_efficiency", 0.60)),
                borehole_correction=float(iv_dict.get("borehole_correction", 1.00)),
                sampler_correction=float(iv_dict.get("sampler_correction", 1.00)),
                rod_length_correction=float(iv_dict.get("rod_length_correction", 1.00)),
            )
            blow_rows = conn.execute(
                "SELECT * FROM blows WHERE interval_id=? ORDER BY blow_number",
                (iv_dict["id"],),
            ).fetchall()
            for br in blow_rows:
                bd = dict(br)
                iv.blows.append(
                    Blow(
                        blow_number=int(bd["blow_number"]),
                        timestamp=datetime.fromisoformat(bd["timestamp"]),
                        depth_mm=float(bd["depth_mm"]),
                        impact_g=float(bd["impact_g"]),
                    )
                )
            test.intervals.append(iv)
        return test
