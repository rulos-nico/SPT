"""
visualization/dashboard.py
Tkinter-based real-time dashboard for the SPT measurement system.

Layout
------
┌─────────────────────────────────────────────────────────────────┐
│  Connection bar  [Port ▼] [Connect] [Start Test] [Stop Test]    │
├──────────────────────────────┬──────────────────────────────────┤
│  Live metrics panel          │  Blow count chart (canvas)       │
│  Depth:  xxx mm              │                                  │
│  Blows:  xx  (current int.)  │                                  │
│  N-value: xx                 │                                  │
├──────────────────────────────┴──────────────────────────────────┤
│  Interval control  [Seating] [Drive 1] [Drive 2] [Zero depth]   │
├─────────────────────────────────────────────────────────────────┤
│  Test metadata  Test ID: ___ BH: ___ Depth(m): ___ Location:   │
├─────────────────────────────────────────────────────────────────┤
│  Log / status text area                                         │
└─────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from ..acquisition.data_processor import DataProcessor
from ..acquisition.serial_reader import SerialReader, SERIAL_AVAILABLE
from ..models.spt_test import Blow, SPTTest
from ..storage.database import Database
from ..storage.exporter import Exporter
from . import charts

logger = logging.getLogger(__name__)

DB_PATH = "spt_measurements.db"


class Dashboard:
    """Main application window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("SPT Measurement System v1.0")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        self._db = Database(DB_PATH)
        self._db.open()

        self._processor = DataProcessor(
            on_blow=self._on_blow,
            on_depth=self._on_depth,
            on_status=self._on_status,
        )
        self._reader = SerialReader(
            self._processor,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
            on_error=self._on_error,
        )

        self._current_test: Optional[SPTTest] = None
        self._current_interval_index: int = 0
        self._blow_counts: list = []   # per-interval blow counts for chart
        self._interval_labels: list = []

        self._build_ui()
        self._refresh_port_list()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        self._build_toolbar()
        self._build_metadata_bar()
        self._build_main_area()
        self._build_interval_bar()
        self._build_log_area()

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=4)
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(3, weight=1)

        ttk.Label(bar, text="Puerto serial:").pack(side=tk.LEFT, padx=2)
        self._port_var = tk.StringVar()
        self._port_combo = ttk.Combobox(
            bar, textvariable=self._port_var, width=14, state="readonly"
        )
        self._port_combo.pack(side=tk.LEFT, padx=2)

        ttk.Button(bar, text="↻", width=2,
                   command=self._refresh_port_list).pack(side=tk.LEFT, padx=1)
        self._connect_btn = ttk.Button(
            bar, text="Connect", command=self._toggle_connection
        )
        self._connect_btn.pack(side=tk.LEFT, padx=4)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=4
        )
        self._start_btn = ttk.Button(
            bar, text="▶ Start Test", command=self._start_test, state=tk.DISABLED
        )
        self._start_btn.pack(side=tk.LEFT, padx=2)
        self._stop_btn = ttk.Button(
            bar, text="■ Stop Test", command=self._stop_test, state=tk.DISABLED
        )
        self._stop_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=4
        )
        ttk.Button(bar, text="Export…", command=self._export_dialog).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(bar, text="History", command=self._show_history).pack(
            side=tk.LEFT, padx=2
        )

        self._conn_lbl = ttk.Label(bar, text="● Disconnected", foreground="red")
        self._conn_lbl.pack(side=tk.RIGHT, padx=6)

    def _build_metadata_bar(self) -> None:
        bar = ttk.LabelFrame(self.root, text="Test Setup", padding=4)
        bar.grid(row=1, column=0, sticky="ew", padx=4, pady=2)
        for i in range(10):
            bar.columnconfigure(i, weight=1)

        fields = [
            ("Test ID:", "test_id", "T001"),
            ("Borehole:", "borehole_id", "BH-1"),
            ("Depth (m):", "test_depth_m", "3.0"),
            ("Location:", "location", ""),
            ("Operator:", "operator", ""),
        ]
        self._meta_vars: dict = {}
        for col, (label, key, default) in enumerate(fields):
            ttk.Label(bar, text=label).grid(row=0, column=col * 2, sticky="e", padx=2)
            var = tk.StringVar(value=default)
            self._meta_vars[key] = var
            ttk.Entry(bar, textvariable=var, width=10).grid(
                row=0, column=col * 2 + 1, sticky="ew", padx=2
            )

    def _build_main_area(self) -> None:
        frame = ttk.Frame(self.root)
        frame.grid(row=2, column=0, sticky="nsew", padx=4, pady=2)
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)

        # Left: live metrics
        metrics = ttk.LabelFrame(frame, text="Live Metrics", padding=8)
        metrics.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        def _metric_row(parent, row, label, default="—"):
            ttk.Label(parent, text=label, font=("", 10)).grid(
                row=row, column=0, sticky="w", pady=2
            )
            var = tk.StringVar(value=default)
            ttk.Label(parent, textvariable=var, font=("", 16, "bold"),
                      foreground="#1a6fa8").grid(
                row=row, column=1, sticky="e", padx=(12, 0)
            )
            return var

        self._depth_var   = _metric_row(metrics, 0, "Depth (mm):")
        self._blows_var   = _metric_row(metrics, 1, "Blows (interval):")
        self._total_var   = _metric_row(metrics, 2, "Total blows:")
        self._nvalue_var  = _metric_row(metrics, 3, "N-value:")
        self._n60_var     = _metric_row(metrics, 4, "N60:")
        self._battery_var = _metric_row(metrics, 5, "Battery (%):")
        self._interval_var= _metric_row(metrics, 6, "Interval:")

        # Right: live blow-count chart
        chart_frame = ttk.LabelFrame(frame, text="Blow Count per Interval", padding=4)
        chart_frame.grid(row=0, column=1, sticky="nsew")
        chart_frame.columnconfigure(0, weight=1)
        chart_frame.rowconfigure(0, weight=1)

        if MATPLOTLIB_AVAILABLE:
            self._fig, self._ax = plt.subplots(figsize=(5, 3))
            self._canvas = FigureCanvasTkAgg(self._fig, master=chart_frame)
            self._canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
            self._update_chart()
        else:
            ttk.Label(chart_frame,
                      text="Install matplotlib for live charts").grid(
                row=0, column=0
            )

    def _build_interval_bar(self) -> None:
        bar = ttk.LabelFrame(self.root, text="Interval Control", padding=4)
        bar.grid(row=3, column=0, sticky="ew", padx=4, pady=2)

        for i, (label, idx) in enumerate([
            ("Seating (0)", 0),
            ("Drive 1 (1)", 1),
            ("Drive 2 (2)", 2),
        ]):
            ttk.Button(
                bar, text=label,
                command=lambda n=idx: self._start_interval(n)
            ).pack(side=tk.LEFT, padx=4)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=4
        )
        ttk.Button(bar, text="Zero Depth",
                   command=self._zero_depth).pack(side=tk.LEFT, padx=4)

        self._hammer_eff_var = tk.StringVar(value="0.60")
        ttk.Label(bar, text="Hammer η:").pack(side=tk.LEFT, padx=(12, 2))
        ttk.Entry(bar, textvariable=self._hammer_eff_var,
                  width=5).pack(side=tk.LEFT)

    def _build_log_area(self) -> None:
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=2)
        log_frame.grid(row=4, column=0, sticky="ew", padx=4, pady=(0, 4))
        log_frame.columnconfigure(0, weight=1)

        self._log = scrolledtext.ScrolledText(
            log_frame, height=5, state=tk.DISABLED, wrap=tk.WORD
        )
        self._log.grid(row=0, column=0, sticky="ew")

    # ── Chart update ───────────────────────────────────────────────────────

    def _update_chart(self) -> None:
        if not MATPLOTLIB_AVAILABLE:
            return
        self._ax.clear()
        if self._blow_counts:
            colors = ["#aaaaaa"] + ["#4a90d9"] * (len(self._blow_counts) - 1)
            self._ax.bar(
                self._interval_labels or list(range(len(self._blow_counts))),
                self._blow_counts,
                color=colors[: len(self._blow_counts)],
                edgecolor="black",
                linewidth=0.5,
            )
            self._ax.set_ylabel("Blows")
        else:
            self._ax.text(0.5, 0.5, "No data yet",
                          ha="center", va="center",
                          transform=self._ax.transAxes)
        self._ax.set_title("Blow Count per Interval", fontsize=9)
        self._fig.tight_layout()
        self._canvas.draw_idle()

    # ── Event callbacks ────────────────────────────────────────────────────

    def _on_blow(self, blow: Blow) -> None:
        self.root.after(0, self._handle_blow_ui, blow)

    def _handle_blow_ui(self, blow: Blow) -> None:
        self._depth_var.set(f"{blow.depth_mm:.1f}")
        proc = self._processor
        interval_blows = proc.current_blow_count
        self._blows_var.set(str(interval_blows))

        if self._current_test:
            total = sum(iv.blow_count()
                        for iv in self._current_test.intervals)
            total += interval_blows
            self._total_var.set(str(total))

        # Update per-interval blow-count list for chart
        idx = self._current_interval_index
        while len(self._blow_counts) <= idx:
            self._blow_counts.append(0)
            self._interval_labels.append(f"Int {len(self._blow_counts)-1}")
        self._blow_counts[idx] = interval_blows
        self._update_chart()
        self._log_message(
            f"Blow {blow.blow_number}: depth={blow.depth_mm:.1f} mm, "
            f"impact={blow.impact_g:.2f} g"
        )

    def _on_depth(self, depth_mm: float) -> None:
        self.root.after(0, lambda: self._depth_var.set(f"{depth_mm:.1f}"))

    def _on_status(self, msg: dict) -> None:
        batt = msg.get("battery_pct", "—")
        self.root.after(0, lambda: self._battery_var.set(str(batt)))

    def _on_connect(self, port: str) -> None:
        self.root.after(0, self._update_connect_ui, True)
        self.root.after(0, self._log_message, f"Connected to {port}")

    def _on_disconnect(self) -> None:
        self.root.after(0, self._update_connect_ui, False)
        self.root.after(0, self._log_message, "Disconnected")

    def _on_error(self, msg: str) -> None:
        self.root.after(0, self._log_message, f"ERROR: {msg}")

    # ── Button handlers ────────────────────────────────────────────────────

    def _refresh_port_list(self) -> None:
        ports = SerialReader.list_ports()
        self._port_combo["values"] = ports
        if ports and not self._port_var.get():
            self._port_var.set(ports[0])

    def _toggle_connection(self) -> None:
        if self._reader.is_connected:
            self._reader.stop()
            self._connect_btn.configure(text="Connect")
        else:
            port = self._port_var.get()
            if not port:
                messagebox.showwarning("No port", "Please select a serial port.")
                return
            if not SERIAL_AVAILABLE:
                messagebox.showwarning(
                    "pyserial missing",
                    "Install pyserial: pip install pyserial"
                )
                return
            self._connect_btn.configure(text="Disconnect")
            self._reader.start(port)

    def _update_connect_ui(self, connected: bool) -> None:
        if connected:
            self._conn_lbl.configure(text="● Connected", foreground="green")
            self._start_btn.configure(state=tk.NORMAL)
        else:
            self._conn_lbl.configure(text="● Disconnected", foreground="red")
            self._start_btn.configure(state=tk.DISABLED)
            self._stop_btn.configure(state=tk.DISABLED)

    def _start_test(self) -> None:
        try:
            depth_m = float(self._meta_vars["test_depth_m"].get())
        except ValueError:
            messagebox.showerror("Invalid input", "Test depth must be a number.")
            return

        test_id    = self._meta_vars["test_id"].get().strip() or "T001"
        borehole   = self._meta_vars["borehole_id"].get().strip() or "BH-1"
        location   = self._meta_vars["location"].get().strip()
        operator   = self._meta_vars["operator"].get().strip()

        self._processor.start_test(
            test_id=test_id,
            borehole_id=borehole,
            test_depth_m=depth_m,
            location=location,
            operator=operator,
        )
        self._blow_counts.clear()
        self._interval_labels.clear()
        self._current_test = None
        self._current_interval_index = 0
        self._update_chart()
        self._nvalue_var.set("—")
        self._n60_var.set("—")

        self._reader.send_command("start")
        self._start_btn.configure(state=tk.DISABLED)
        self._stop_btn.configure(state=tk.NORMAL)
        self._log_message(f"Test {test_id} started at {depth_m} m")

    def _stop_test(self) -> None:
        self._reader.send_command("stop")
        test = self._processor.finish_test()
        if test:
            self._current_test = test
            self._db.save_test(test)
            n  = test.n_value()
            n60 = test.n60()
            self._nvalue_var.set(str(n) if n is not None else "—")
            self._n60_var.set(str(n60) if n60 is not None else "—")
            self._log_message(
                f"Test {test.test_id} completed – N={n}, N60={n60}, "
                f"total blows={test.total_blows()}"
            )
        self._start_btn.configure(state=tk.NORMAL)
        self._stop_btn.configure(state=tk.DISABLED)

    def _start_interval(self, idx: int) -> None:
        depth_mm = self._processor.last_depth_mm
        try:
            eta = float(self._hammer_eff_var.get())
        except ValueError:
            eta = 0.60
        self._processor.start_interval(
            interval_index=idx,
            start_depth_mm=depth_mm,
            hammer_efficiency=eta,
        )
        self._current_interval_index = idx
        self._interval_var.set(f"Interval {idx}")
        self._blows_var.set("0")
        self._log_message(
            f"Interval {idx} started at {depth_mm:.1f} mm, η={eta}"
        )

    def _zero_depth(self) -> None:
        self._reader.send_command("zero")
        self._depth_var.set("0.0")
        self._log_message("Depth zeroed")

    def _export_dialog(self) -> None:
        if not self._current_test:
            messagebox.showinfo("No test", "No completed test to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[
                ("JSON", "*.json"),
                ("CSV blows", "*.csv"),
                ("CSV summary", "*.csv"),
            ],
            initialfile=f"{self._current_test.test_id}_export",
        )
        if not path:
            return
        if path.endswith(".json"):
            Exporter.to_json(self._current_test, path)
        else:
            Exporter.to_csv_blows(self._current_test, path)
        self._log_message(f"Exported to {path}")
        messagebox.showinfo("Export", f"Saved to:\n{path}")

    def _show_history(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Test History")
        win.geometry("700x400")

        tree = ttk.Treeview(
            win,
            columns=("test_id", "borehole_id", "date", "depth_m",
                     "n_value", "n60", "blows"),
            show="headings",
        )
        for col, head, w in [
            ("test_id",    "Test ID",    90),
            ("borehole_id","Borehole",   80),
            ("date",       "Date",      140),
            ("depth_m",    "Depth (m)",  70),
            ("n_value",    "N-value",    70),
            ("n60",        "N60",        70),
            ("blows",      "Blows",      60),
        ]:
            tree.heading(col, text=head)
            tree.column(col, width=w, anchor=tk.CENTER)

        sb = ttk.Scrollbar(win, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        for test in self._db.list_tests():
            tree.insert("", tk.END, values=(
                test.test_id,
                test.borehole_id,
                test.date.strftime("%Y-%m-%d %H:%M"),
                f"{test.test_depth_m:.2f}",
                test.n_value() or "—",
                test.n60()     or "—",
                test.total_blows(),
            ))

    # ── Log helper ─────────────────────────────────────────────────────────

    def _log_message(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        full = f"[{ts}] {msg}\n"
        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, full)
        self._log.see(tk.END)
        self._log.configure(state=tk.DISABLED)

    # ── Application lifecycle ──────────────────────────────────────────────

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self) -> None:
        if self._reader.is_connected:
            self._reader.stop()
        self._db.close()
        self.root.destroy()
