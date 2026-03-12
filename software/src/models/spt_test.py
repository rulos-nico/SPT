"""
models/spt_test.py
Data models for the SPT (Standard Penetration Test) measurement system.

SPT terminology used here:
- Session:   one physical test session at a location, contains one or more
             SPT interval tests.
- Interval:  a 150 mm penetration interval (seating 150 mm + three 150 mm
             drive intervals are typical, but configurable).
- Blow:      a single hammer impact recorded with timestamp, depth and
             impact acceleration.
- N-value:   blow count for a 300 mm interval (blow count for intervals 2+3,
             discarding the seating interval).
- N60:       energy-corrected N-value normalised to 60 % hammer efficiency.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Blow:
    """A single recorded hammer blow."""
    blow_number: int
    timestamp: datetime
    depth_mm: float
    impact_g: float

    def to_dict(self) -> dict:
        return {
            "blow_number": self.blow_number,
            "timestamp": self.timestamp.isoformat(),
            "depth_mm": round(self.depth_mm, 1),
            "impact_g": round(self.impact_g, 2),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Blow":
        return cls(
            blow_number=int(d["blow_number"]),
            timestamp=datetime.fromisoformat(d["timestamp"]),
            depth_mm=float(d["depth_mm"]),
            impact_g=float(d["impact_g"]),
        )


@dataclass
class SPTInterval:
    """
    One 150 mm penetration interval.

    :param interval_index:  0 = seating interval, 1/2 = first/second drive.
    :param start_depth_mm:  Depth at the start of this interval.
    """
    interval_index: int
    start_depth_mm: float
    end_depth_mm: float = 0.0
    blows: List[Blow] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Corrections applied when computing N60
    hammer_efficiency: float = 0.60   # Em (0.0–1.0)
    borehole_correction: float = 1.00  # Cb
    sampler_correction: float = 1.00   # Cs
    rod_length_correction: float = 1.00  # Cr

    def blow_count(self) -> int:
        """Number of blows recorded in this interval."""
        return len(self.blows)

    def penetration_mm(self) -> float:
        """Actual penetration achieved (end – start)."""
        return self.end_depth_mm - self.start_depth_mm

    def n_value(self) -> int:
        """Raw N-value (blow count for this interval)."""
        return self.blow_count()

    def n60(self) -> float:
        """
        Energy-corrected N-value normalised to 60 % hammer efficiency.
        N60 = N * (Em * Cb * Cs * Cr) / 0.60
        """
        correction = (
            self.hammer_efficiency
            * self.borehole_correction
            * self.sampler_correction
            * self.rod_length_correction
        ) / 0.60
        return round(self.n_value() * correction, 1)

    def to_dict(self) -> dict:
        return {
            "interval_index": self.interval_index,
            "start_depth_mm": round(self.start_depth_mm, 1),
            "end_depth_mm": round(self.end_depth_mm, 1),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "hammer_efficiency": self.hammer_efficiency,
            "borehole_correction": self.borehole_correction,
            "sampler_correction": self.sampler_correction,
            "rod_length_correction": self.rod_length_correction,
            "blow_count": self.blow_count(),
            "n60": self.n60(),
            "blows": [b.to_dict() for b in self.blows],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SPTInterval":
        obj = cls(
            interval_index=int(d["interval_index"]),
            start_depth_mm=float(d["start_depth_mm"]),
            end_depth_mm=float(d["end_depth_mm"]),
            start_time=datetime.fromisoformat(d["start_time"]) if d.get("start_time") else None,
            end_time=datetime.fromisoformat(d["end_time"]) if d.get("end_time") else None,
            hammer_efficiency=float(d.get("hammer_efficiency", 0.60)),
            borehole_correction=float(d.get("borehole_correction", 1.00)),
            sampler_correction=float(d.get("sampler_correction", 1.00)),
            rod_length_correction=float(d.get("rod_length_correction", 1.00)),
        )
        obj.blows = [Blow.from_dict(b) for b in d.get("blows", [])]
        return obj


@dataclass
class SPTTest:
    """
    A complete SPT test at a single depth.

    Typically composed of a 150 mm seating interval followed by two (or
    three) 150 mm drive intervals.  The N-value is the combined blow count
    of the two drive intervals (discarding the seating interval).
    """
    test_id: str
    borehole_id: str
    test_depth_m: float          # depth to top of sampler (metres)
    date: datetime
    location: str = ""
    operator: str = ""
    intervals: List[SPTInterval] = field(default_factory=list)

    def n_value(self) -> Optional[int]:
        """
        Standard N-value: sum of blows in drive intervals (index ≥ 1).
        Returns None if fewer than two drive intervals are recorded.
        """
        drive = [iv for iv in self.intervals if iv.interval_index >= 1]
        if len(drive) < 2:
            return None
        return sum(iv.blow_count() for iv in drive[:2])

    def n60(self) -> Optional[float]:
        """
        Combined N60 from the two drive intervals.
        Returns None if fewer than two drive intervals are recorded.
        """
        drive = [iv for iv in self.intervals if iv.interval_index >= 1]
        if len(drive) < 2:
            return None
        return round(sum(iv.n60() for iv in drive[:2]), 1)

    def total_blows(self) -> int:
        """Total blows across all intervals."""
        return sum(iv.blow_count() for iv in self.intervals)

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "borehole_id": self.borehole_id,
            "test_depth_m": round(self.test_depth_m, 2),
            "date": self.date.isoformat(),
            "location": self.location,
            "operator": self.operator,
            "n_value": self.n_value(),
            "n60": self.n60(),
            "total_blows": self.total_blows(),
            "intervals": [iv.to_dict() for iv in self.intervals],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SPTTest":
        obj = cls(
            test_id=d["test_id"],
            borehole_id=d["borehole_id"],
            test_depth_m=float(d["test_depth_m"]),
            date=datetime.fromisoformat(d["date"]),
            location=d.get("location", ""),
            operator=d.get("operator", ""),
        )
        obj.intervals = [SPTInterval.from_dict(iv) for iv in d.get("intervals", [])]
        return obj

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "SPTTest":
        return cls.from_dict(json.loads(json_str))
