"""
visualization/charts.py
Matplotlib-based chart helpers for SPT data.
"""

from __future__ import annotations

from typing import List, Optional

try:
    import matplotlib
    matplotlib.use("Agg")   # non-interactive backend for testing / headless use
    import matplotlib.pyplot as plt
    import matplotlib.figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from ..models.spt_test import SPTTest


def _require_matplotlib() -> None:
    if not MATPLOTLIB_AVAILABLE:
        raise ImportError(
            "matplotlib is required for chart generation. "
            "Run: pip install matplotlib"
        )


def plot_blows_vs_depth(
    test: SPTTest,
    ax: Optional["matplotlib.axes.Axes"] = None,
    title: Optional[str] = None,
) -> "matplotlib.figure.Figure":
    """
    Horizontal bar chart: blow count per interval vs depth (classic SPT log).

    Each interval is drawn as a bar whose length equals its blow count.
    Drive intervals (index ≥ 1) are shaded differently from the seating
    interval.
    """
    _require_matplotlib()

    fig, ax_out = (plt.subplots(figsize=(6, 4)) if ax is None else (ax.figure, ax))

    depths = []
    blows  = []
    colors = []
    for iv in test.intervals:
        mid = (iv.start_depth_mm + iv.end_depth_mm) / 2.0
        depths.append(mid / 1000.0)   # convert to metres for readability
        blows.append(iv.blow_count())
        colors.append("#4a90d9" if iv.interval_index >= 1 else "#aaaaaa")

    ax_out.barh(
        [f"Int {iv.interval_index}\n({iv.start_depth_mm:.0f}–{iv.end_depth_mm:.0f} mm)"
         for iv in test.intervals],
        blows,
        color=colors,
        edgecolor="black",
        linewidth=0.5,
    )
    ax_out.set_xlabel("Blow count")
    ax_out.set_title(
        title or f"SPT Blow Count – {test.test_id} ({test.borehole_id})"
    )
    ax_out.invert_yaxis()
    n = test.n_value()
    if n is not None:
        ax_out.axvline(x=n, color="red", linestyle="--", linewidth=1,
                       label=f"N={n}")
        ax_out.legend()
    fig.tight_layout()
    return fig


def plot_depth_vs_time(
    test: SPTTest,
    ax: Optional["matplotlib.axes.Axes"] = None,
    title: Optional[str] = None,
) -> "matplotlib.figure.Figure":
    """
    Line chart: sampler depth (mm) over time (seconds from test start).
    """
    _require_matplotlib()

    fig, ax_out = (plt.subplots(figsize=(8, 4)) if ax is None else (ax.figure, ax))

    all_blows = [b for iv in test.intervals for b in iv.blows]
    if not all_blows:
        ax_out.set_title("No blow data")
        return fig

    t0 = all_blows[0].timestamp
    times  = [(b.timestamp - t0).total_seconds() for b in all_blows]
    depths = [b.depth_mm for b in all_blows]

    ax_out.plot(times, depths, marker="o", markersize=3, linewidth=1.5,
                color="#2ecc71")
    ax_out.set_xlabel("Time (s)")
    ax_out.set_ylabel("Depth (mm)")
    ax_out.set_title(title or f"Penetration vs Time – {test.test_id}")
    fig.tight_layout()
    return fig


def plot_impact_acceleration(
    test: SPTTest,
    ax: Optional["matplotlib.axes.Axes"] = None,
    title: Optional[str] = None,
) -> "matplotlib.figure.Figure":
    """
    Scatter plot: impact acceleration (g) for each blow.
    """
    _require_matplotlib()

    fig, ax_out = (plt.subplots(figsize=(8, 4)) if ax is None else (ax.figure, ax))

    all_blows = [b for iv in test.intervals for b in iv.blows]
    if not all_blows:
        ax_out.set_title("No blow data")
        return fig

    blow_numbers = [b.blow_number for b in all_blows]
    impact_g     = [b.impact_g    for b in all_blows]

    ax_out.scatter(blow_numbers, impact_g, s=20, color="#e74c3c", alpha=0.7)
    ax_out.set_xlabel("Blow number")
    ax_out.set_ylabel("Impact acceleration (g)")
    ax_out.set_title(title or f"Impact Acceleration – {test.test_id}")
    ax_out.axhline(y=sum(impact_g) / len(impact_g),
                   color="navy", linestyle="--", linewidth=1, label="Mean")
    ax_out.legend()
    fig.tight_layout()
    return fig


def plot_n_profile(
    tests: List[SPTTest],
    ax: Optional["matplotlib.axes.Axes"] = None,
    title: Optional[str] = None,
    use_n60: bool = True,
) -> "matplotlib.figure.Figure":
    """
    N-value (or N60) profile: depth (m) vs blow count for a borehole.
    Tests are sorted by depth and plotted as a step-profile.
    """
    _require_matplotlib()

    fig, ax_out = (plt.subplots(figsize=(5, 8)) if ax is None else (ax.figure, ax))

    sorted_tests = sorted(tests, key=lambda t: t.test_depth_m)
    depths  = []
    n_vals  = []
    for t in sorted_tests:
        n = t.n60() if use_n60 else t.n_value()
        if n is not None:
            depths.append(t.test_depth_m)
            n_vals.append(n)

    if n_vals:
        ax_out.step(n_vals, depths, where="post", linewidth=2, color="#2980b9")
        ax_out.scatter(n_vals, depths, s=40, color="#2980b9", zorder=5)

    ax_out.invert_yaxis()
    ax_out.set_xlabel("N60" if use_n60 else "N-value")
    ax_out.set_ylabel("Depth (m)")
    ax_out.set_title(title or ("N60 Profile" if use_n60 else "N-value Profile"))
    fig.tight_layout()
    return fig


def save_figure(fig: "matplotlib.figure.Figure", path: str, dpi: int = 150) -> None:
    """Save a figure to disk."""
    _require_matplotlib()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
