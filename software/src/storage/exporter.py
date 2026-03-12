"""
storage/exporter.py
Exports SPT test data to CSV and JSON formats.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import List

from ..models.spt_test import SPTTest

logger = logging.getLogger(__name__)


class Exporter:
    """
    Export one or multiple SPTTest objects to files.

    Supported formats
    -----------------
    * JSON  – full nested representation including all blows.
    * CSV   – two files: one summary row per test, one row per blow.
    """

    # ── JSON export ────────────────────────────────────────────────────────

    @staticmethod
    def to_json(test: SPTTest, path: str) -> None:
        """Write a single test to a pretty-printed JSON file."""
        dest = Path(path)
        dest.write_text(test.to_json(), encoding="utf-8")
        logger.info("Exported JSON to %s", dest)

    @staticmethod
    def tests_to_json(tests: List[SPTTest], path: str) -> None:
        """Write multiple tests to a JSON array file."""
        dest = Path(path)
        data = [t.to_dict() for t in tests]
        dest.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Exported %d tests to JSON %s", len(tests), dest)

    # ── CSV export ─────────────────────────────────────────────────────────

    @staticmethod
    def to_csv_summary(tests: List[SPTTest], path: str) -> None:
        """
        Write one summary row per test to a CSV file.

        Columns: test_id, borehole_id, date, location, operator,
                 test_depth_m, n_value, n60, total_blows
        """
        dest = Path(path)
        fieldnames = [
            "test_id", "borehole_id", "date", "location", "operator",
            "test_depth_m", "n_value", "n60", "total_blows",
        ]
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for test in tests:
                writer.writerow({
                    "test_id":      test.test_id,
                    "borehole_id":  test.borehole_id,
                    "date":         test.date.isoformat(),
                    "location":     test.location,
                    "operator":     test.operator,
                    "test_depth_m": round(test.test_depth_m, 2),
                    "n_value":      test.n_value(),
                    "n60":          test.n60(),
                    "total_blows":  test.total_blows(),
                })
        logger.info("Exported %d test summaries to CSV %s", len(tests), dest)

    @staticmethod
    def to_csv_blows(test: SPTTest, path: str) -> None:
        """
        Write one row per blow for a single test to a CSV file.

        Columns: test_id, borehole_id, interval_index, blow_number,
                 timestamp, depth_mm, impact_g
        """
        dest = Path(path)
        fieldnames = [
            "test_id", "borehole_id", "interval_index",
            "blow_number", "timestamp", "depth_mm", "impact_g",
        ]
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for iv in test.intervals:
                for blow in iv.blows:
                    writer.writerow({
                        "test_id":        test.test_id,
                        "borehole_id":    test.borehole_id,
                        "interval_index": iv.interval_index,
                        "blow_number":    blow.blow_number,
                        "timestamp":      blow.timestamp.isoformat(),
                        "depth_mm":       round(blow.depth_mm, 1),
                        "impact_g":       round(blow.impact_g, 2),
                    })
        logger.info(
            "Exported %d blows for test %s to CSV %s",
            test.total_blows(),
            test.test_id,
            dest,
        )

    @staticmethod
    def to_csv_intervals(test: SPTTest, path: str) -> None:
        """
        Write one row per interval for a single test to a CSV file.

        Columns: test_id, borehole_id, interval_index, start_depth_mm,
                 end_depth_mm, blow_count, n60, hammer_efficiency,
                 borehole_correction, sampler_correction, rod_length_correction
        """
        dest = Path(path)
        fieldnames = [
            "test_id", "borehole_id", "interval_index",
            "start_depth_mm", "end_depth_mm", "blow_count", "n60",
            "hammer_efficiency", "borehole_correction",
            "sampler_correction", "rod_length_correction",
        ]
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for iv in test.intervals:
                writer.writerow({
                    "test_id":               test.test_id,
                    "borehole_id":           test.borehole_id,
                    "interval_index":        iv.interval_index,
                    "start_depth_mm":        round(iv.start_depth_mm, 1),
                    "end_depth_mm":          round(iv.end_depth_mm, 1),
                    "blow_count":            iv.blow_count(),
                    "n60":                   iv.n60(),
                    "hammer_efficiency":     iv.hammer_efficiency,
                    "borehole_correction":   iv.borehole_correction,
                    "sampler_correction":    iv.sampler_correction,
                    "rod_length_correction": iv.rod_length_correction,
                })
        logger.info(
            "Exported %d intervals for test %s to CSV %s",
            len(test.intervals),
            test.test_id,
            dest,
        )
