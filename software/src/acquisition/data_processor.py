"""
acquisition/data_processor.py
Processes raw JSON messages received from the embedded device and converts
them into Blow, SPTInterval and SPTTest domain objects.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Callable, List, Optional

from ..models.spt_test import Blow, SPTInterval, SPTTest

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Stateful processor for the device's JSON event stream.

    Usage::

        processor = DataProcessor(on_blow=my_callback, on_depth=depth_cb)
        processor.start_test(test_id="T01", borehole_id="BH-1",
                             test_depth_m=3.0, location="Site A")
        processor.start_interval(interval_index=0, start_depth_mm=3000.0)

        for json_line in serial_port:
            processor.process_line(json_line)

        test = processor.finish_test()
    """

    def __init__(
        self,
        on_blow: Optional[Callable[[Blow], None]] = None,
        on_depth: Optional[Callable[[float], None]] = None,
        on_status: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self._on_blow = on_blow
        self._on_depth = on_depth
        self._on_status = on_status

        self._current_test: Optional[SPTTest] = None
        self._current_interval: Optional[SPTInterval] = None
        self._last_depth_mm: float = 0.0
        self._raw_lines: List[str] = []

    # ── Public API ─────────────────────────────────────────────────────────

    def start_test(
        self,
        test_id: str,
        borehole_id: str,
        test_depth_m: float,
        location: str = "",
        operator: str = "",
    ) -> None:
        """Initialise a new SPT test."""
        self._current_test = SPTTest(
            test_id=test_id,
            borehole_id=borehole_id,
            test_depth_m=test_depth_m,
            date=datetime.now(timezone.utc),
            location=location,
            operator=operator,
        )
        self._current_interval = None
        self._last_depth_mm = 0.0
        self._raw_lines = []
        logger.info("Started test %s at %.2f m", test_id, test_depth_m)

    def start_interval(
        self,
        interval_index: int,
        start_depth_mm: float,
        hammer_efficiency: float = 0.60,
        borehole_correction: float = 1.00,
        sampler_correction: float = 1.00,
        rod_length_correction: float = 1.00,
    ) -> None:
        """Close the previous interval (if any) and open a new one."""
        if self._current_test is None:
            raise RuntimeError("Call start_test() before start_interval()")
        if self._current_interval is not None:
            self._close_current_interval(start_depth_mm)

        self._current_interval = SPTInterval(
            interval_index=interval_index,
            start_depth_mm=start_depth_mm,
            hammer_efficiency=hammer_efficiency,
            borehole_correction=borehole_correction,
            sampler_correction=sampler_correction,
            rod_length_correction=rod_length_correction,
            start_time=datetime.now(timezone.utc),
        )
        logger.info(
            "Started interval %d at %.1f mm", interval_index, start_depth_mm
        )

    def finish_test(self) -> Optional[SPTTest]:
        """Close the current interval and return the completed test object."""
        if self._current_test is None:
            return None
        if self._current_interval is not None:
            self._close_current_interval(self._last_depth_mm)
        test = self._current_test
        self._current_test = None
        self._current_interval = None
        logger.info(
            "Finished test %s – N=%s, N60=%s",
            test.test_id,
            test.n_value(),
            test.n60(),
        )
        return test

    def process_line(self, line: str) -> None:
        """Parse one JSON line from the device and dispatch to handlers."""
        line = line.strip()
        if not line:
            return
        self._raw_lines.append(line)
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Non-JSON line ignored: %r", line)
            return

        msg_type = msg.get("type", "")
        if msg_type == "blow":
            self._handle_blow(msg)
        elif msg_type == "depth":
            self._handle_depth(msg)
        elif msg_type == "status":
            self._handle_status(msg)
        elif msg_type in ("ack", "ready", "error"):
            logger.debug("Device message: %s", line)
        else:
            logger.debug("Unknown message type %r ignored", msg_type)

    @property
    def last_depth_mm(self) -> float:
        """Most recently received depth in millimetres."""
        return self._last_depth_mm

    @property
    def current_blow_count(self) -> int:
        """Blow count in the currently open interval."""
        if self._current_interval is None:
            return 0
        return self._current_interval.blow_count()

    # ── Private helpers ────────────────────────────────────────────────────

    def _ts_from_msg(self, msg: dict) -> datetime:
        """Convert Unix epoch in message to aware datetime."""
        ts = msg.get("ts", 0)
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return datetime.now(timezone.utc)

    def _handle_blow(self, msg: dict) -> None:
        blow = Blow(
            blow_number=int(msg.get("blow", 0)),
            timestamp=self._ts_from_msg(msg),
            depth_mm=float(msg.get("depth_mm", self._last_depth_mm)),
            impact_g=float(msg.get("impact_g", 0.0)),
        )
        self._last_depth_mm = blow.depth_mm

        if self._current_interval is not None:
            self._current_interval.blows.append(blow)

        if self._on_blow:
            self._on_blow(blow)

    def _handle_depth(self, msg: dict) -> None:
        depth_mm = float(msg.get("depth_mm", self._last_depth_mm))
        self._last_depth_mm = depth_mm
        if self._on_depth:
            self._on_depth(depth_mm)

    def _handle_status(self, msg: dict) -> None:
        if self._on_status:
            self._on_status(msg)

    def _close_current_interval(self, end_depth_mm: float) -> None:
        iv = self._current_interval
        if iv is None:
            return
        iv.end_depth_mm = end_depth_mm
        iv.end_time = datetime.now(timezone.utc)
        if self._current_test is not None:
            self._current_test.intervals.append(iv)
        self._current_interval = None
