from __future__ import annotations

import re
from collections import deque
from typing import Deque, Optional, Tuple

import numpy as np
import pyqtgraph as pg
from pyqtgraph import AxisItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from polymarket_analyzer.core.gamma import floor_interval_epoch_sec

_SLUG_TAIL = re.compile(r"-(\d+)m-(\d+)$")


def _parse_market_slug(slug: str) -> Optional[Tuple[int, int]]:
    """Return (bucket_start_epoch_sec, interval_minutes) or None."""
    m = _SLUG_TAIL.search(slug.strip())
    if not m:
        return None
    return int(m.group(2)), int(m.group(1))


class _ProbAxis01(AxisItem):
    """Y axis 0–1 with tick positions every 0.01."""

    def tickValues(self, minVal: float, maxVal: float, size: float) -> list[tuple[float, list[float]]]:
        ticks = [round(i * 0.01, 2) for i in range(101)]
        return [(0.01, ticks)]

    def tickStrings(self, values: list, scale: float, spacing: float) -> list[str]:
        return [f"{float(v):.2f}" for v in values]


class _MarketTimeXAxis(AxisItem):
    """X axis 0 … full market length; labels as M:SS."""

    def __init__(self, *args, duration_sec: float = 300.0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._duration_sec = max(1.0, float(duration_sec))

    def set_duration_sec(self, duration_sec: float) -> None:
        self._duration_sec = max(1.0, float(duration_sec))
        self.picture = None

    def tickValues(self, minVal: float, maxVal: float, size: float) -> list[tuple[float, list[float]]]:
        d = self._duration_sec
        # ~6–8 ticks across the window
        target = max(5, int(size / 80))
        raw_step = d / target
        if raw_step <= 15:
            step = 10.0
        elif raw_step <= 45:
            step = 30.0
        elif raw_step <= 90:
            step = 60.0
        else:
            step = 120.0
        ticks: list[float] = [0.0]
        t = step
        while t < d - 1e-6:
            ticks.append(round(t, 2))
            t += step
        if not ticks or abs(ticks[-1] - d) > 1e-3:
            ticks.append(round(d, 2))
        return [(step, ticks)]

    def tickStrings(self, values: list, scale: float, spacing: float) -> list[str]:
        out: list[str] = []
        for v in values:
            sec = int(round(float(v)))
            out.append(f"{sec // 60}:{sec % 60:02d}")
        return out


class MidPriceChart(QWidget):
    """UP outcome price is ``mid``; DOWN outcome price is ``1 - mid``, vs time in the current bucket."""

    def __init__(self, *, interval_minutes: int = 5, max_points: int = 100_000) -> None:
        super().__init__()
        self._fallback_interval_min = max(1, min(60, int(interval_minutes)))
        self._duration_sec = float(self._fallback_interval_min * 60)
        self._max_points = int(max_points)
        self._points: Deque[tuple[float, float]] = deque(maxlen=self._max_points)

        self._x_axis = _MarketTimeXAxis(orientation="bottom", duration_sec=self._duration_sec)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget(
            axisItems={
                "left": _ProbAxis01(orientation="left"),
                "bottom": self._x_axis,
            }
        )
        self._plot.setBackground("#ffffff")
        self._plot.showGrid(x=True, y=True, alpha=0.35)
        self._plot.setLabel("left", "UP = mid, DOWN = 1 − mid (probability 0–1)")
        self._plot.setLabel("bottom", "Time in market (full window)")
        self._plot.setMouseEnabled(x=True, y=False)

        ref_pen_outer = pg.mkPen("#9e9e9e", width=1, style=Qt.PenStyle.DotLine)
        ref_pen_mid = pg.mkPen("#757575", width=1, style=Qt.PenStyle.DashLine)
        for y, pen in (
            (0.8, ref_pen_outer),
            (0.2, ref_pen_outer),
            (0.5, ref_pen_mid),
        ):
            ln = pg.InfiniteLine(pos=y, angle=0, movable=False, pen=pen)
            ln.setZValue(-5)
            self._plot.addItem(ln)

        ax_left = self._plot.getAxis("left")
        tick_font = QFont()
        tick_font.setPointSize(8)
        ax_left.setTickFont(tick_font)

        self._plot.addLegend(offset=(10, 10))
        pen_mid = pg.mkPen("#1565c0", width=2)
        pen_mir = pg.mkPen("#c62828", width=2, style=Qt.PenStyle.DashLine)
        self._curve_mid = self._plot.plot([], [], pen=pen_mid, name="UP price (mid)")
        self._curve_mirror = self._plot.plot([], [], pen=pen_mir, name="DOWN price (1 − mid)")

        vb = self._plot.getViewBox()
        vb.setMouseEnabled(x=True, y=False)
        self._plot.setYRange(0.0, 1.0, padding=0.0)
        self._plot.setXRange(0.0, self._duration_sec, padding=0.02)

        layout.addWidget(self._plot)
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._plot.setMinimumHeight(300)
        self._plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def clear_series(self) -> None:
        self._points.clear()
        self._curve_mid.setData([], [])
        self._curve_mirror.setData([], [])
        self._plot.setYRange(0.0, 1.0, padding=0.0)
        self._plot.setXRange(0.0, self._duration_sec, padding=0.02)

    def set_fallback_interval_minutes(self, interval_minutes: int) -> None:
        """Used when slug cannot be parsed (should be rare)."""
        self._fallback_interval_min = max(1, min(60, int(interval_minutes)))
        self._duration_sec = float(self._fallback_interval_min * 60)
        self._x_axis.set_duration_sec(self._duration_sec)
        self._plot.setXRange(0.0, self._duration_sec, padding=0.02)

    def add_mid(self, updated_at_ms: int, mid: Optional[float], slug: str) -> None:
        if mid is None or mid != mid:  # NaN
            return
        m = max(0.0, min(1.0, float(mid)))

        parsed = _parse_market_slug(slug)
        if parsed:
            epoch_sec, interval_min = parsed
            interval_min = max(1, min(60, interval_min))
            dur = float(interval_min * 60)
        else:
            now_sec = int(updated_at_ms // 1000)
            im = self._fallback_interval_min
            epoch_sec = floor_interval_epoch_sec(now_sec, im)
            dur = float(im * 60)

        if abs(dur - self._duration_sec) > 1e-6:
            self._duration_sec = dur
            self._x_axis.set_duration_sec(dur)

        market_start_ms = epoch_sec * 1000
        x = (updated_at_ms - market_start_ms) / 1000.0
        x = max(0.0, min(self._duration_sec, x))

        if self._points and self._points[-1][0] == x:
            self._points.pop()
        self._points.append((x, m))

        xs = np.array([p[0] for p in self._points], dtype=float)
        ys = np.array([p[1] for p in self._points], dtype=float)
        ys_m = 1.0 - ys
        self._curve_mid.setData(xs, ys)
        self._curve_mirror.setData(xs, ys_m)

        if len(xs) == 0:
            return

        self._plot.setXRange(0.0, self._duration_sec, padding=0.02)
        self._plot.setYRange(0.0, 1.0, padding=0.0)
