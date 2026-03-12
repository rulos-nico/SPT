"""
main.py
SPT Measurement System – application entry point.

Usage
-----
    python main.py              # Launch GUI dashboard
    python main.py --demo       # Run a demo simulation (no hardware needed)
    python main.py --help       # Show this help
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("spt")


def run_gui() -> None:
    """Launch the Tkinter dashboard."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        logger.error(
            "tkinter is not available on this system. "
            "Install it via your OS package manager (e.g. "
            "'sudo apt install python3-tk')."
        )
        sys.exit(1)

    from src.visualization.dashboard import Dashboard
    app = Dashboard()
    app.run()


def run_demo() -> None:
    """
    Simulate an SPT test without real hardware.
    Feeds synthetic JSON lines into the DataProcessor and prints results.
    """
    from src.acquisition.data_processor import DataProcessor
    from src.models.spt_test import SPTTest

    print("=" * 60)
    print("SPT Measurement System – Demo Simulation")
    print("=" * 60)

    blows_received = []

    def on_blow(blow):
        blows_received.append(blow)
        print(
            f"  [BLOW] #{blow.blow_number:3d} | "
            f"depth={blow.depth_mm:6.1f} mm | "
            f"impact={blow.impact_g:.2f} g | "
            f"ts={blow.timestamp.strftime('%H:%M:%S')}"
        )

    def on_depth(depth_mm):
        pass  # quiet for demo

    processor = DataProcessor(on_blow=on_blow, on_depth=on_depth)

    # Simulate 3 intervals: seating + 2 drive intervals
    test_id = f"DEMO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    processor.start_test(
        test_id=test_id,
        borehole_id="BH-DEMO",
        test_depth_m=3.0,
        location="Demo Site",
        operator="Auto",
    )

    intervals = [
        (0, 0.0,    150.0, 4),    # seating: 4 blows
        (1, 150.0,  300.0, 8),    # drive 1: 8 blows
        (2, 300.0,  450.0, 10),   # drive 2: 10 blows
    ]

    import random
    random.seed(42)
    blow_seq = 1
    base_ts = int(datetime.now(timezone.utc).timestamp())

    for iv_idx, start_mm, end_mm, n_blows in intervals:
        processor.start_interval(iv_idx, start_mm)
        print(f"\nInterval {iv_idx} ({start_mm:.0f}–{end_mm:.0f} mm)")

        step = (end_mm - start_mm) / n_blows
        for i in range(n_blows):
            depth_mm = start_mm + (i + 1) * step
            msg = json.dumps({
                "type":     "blow",
                "ts":       base_ts + blow_seq * 3,
                "blow":     blow_seq,
                "depth_mm": round(depth_mm, 1),
                "impact_g": round(random.uniform(5.0, 12.0), 2),
            })
            processor.process_line(msg)
            blow_seq += 1
            time.sleep(0.01)   # small delay so demo isn't instantaneous

    test = processor.finish_test()
    if test:
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"  Test ID    : {test.test_id}")
        print(f"  Borehole   : {test.borehole_id}")
        print(f"  Depth      : {test.test_depth_m} m")
        print(f"  N-value    : {test.n_value()}")
        print(f"  N60        : {test.n60()}")
        print(f"  Total blows: {test.total_blows()}")
        print()
        print("Interval details:")
        for iv in test.intervals:
            label = "Seating " if iv.interval_index == 0 else f"Drive {iv.interval_index}"
            print(
                f"  {label:8s} | blows={iv.blow_count():3d} | "
                f"n60={iv.n60():5.1f} | "
                f"{iv.start_depth_mm:.0f}–{iv.end_depth_mm:.0f} mm"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SPT Measurement System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a demo simulation without hardware",
    )
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        run_gui()


if __name__ == "__main__":
    main()
