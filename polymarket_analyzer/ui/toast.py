"""Lightweight non-modal toasts anchored to the bottom-right of a host widget."""

from __future__ import annotations

from functools import partial
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


class ToastManager:
    """Queue-friendly toast overlay; safe to call from asyncio via ``schedule``."""

    def __init__(self, host: QWidget) -> None:
        self._host = host
        self._frame: Optional[QFrame] = None
        self._label: Optional[QLabel] = None
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide)
        self._queue: list[tuple[str, str, int]] = []
        self._busy = False

    def schedule(self, message: str, *, kind: str = "info", duration_ms: int = 5000) -> None:
        QTimer.singleShot(0, partial(self._enqueue, message, kind, duration_ms))

    def _enqueue(self, message: str, kind: str, duration_ms: int) -> None:
        self._queue.append((message, kind, duration_ms))
        if not self._busy:
            self._show_next()

    def _show_next(self) -> None:
        if not self._queue:
            self._busy = False
            return
        self._busy = True
        msg, kind, duration_ms = self._queue.pop(0)
        self._show_now(msg, kind, duration_ms)

    def reposition_if_visible(self) -> None:
        if self._frame is not None and self._frame.isVisible():
            self._place_frame()

    def _ensure_frame(self) -> None:
        if self._frame is not None:
            return
        fr = QFrame(self._host)
        fr.setObjectName("pmToastFrame")
        fr.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(fr)
        lay.setContentsMargins(12, 10, 12, 10)
        lbl = QLabel(fr)
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(420)
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        lay.addWidget(lbl)
        fr.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._frame = fr
        self._label = lbl

    def _style_for(self, kind: str) -> str:
        base = (
            "#pmToastFrame { border-radius: 8px; border: 1px solid #b8c0cc; background-color: %s; } "
            "QLabel { color: #1c2330; font-size: 12px; }"
        )
        if kind == "error":
            return base % "#f8d7da"
        if kind == "warn":
            return base % "#fff3cd"
        return base % "#d1ecf1"

    def _show_now(self, message: str, kind: str, duration_ms: int) -> None:
        self._ensure_frame()
        assert self._frame is not None and self._label is not None
        self._frame.setStyleSheet(self._style_for(kind))
        self._label.setText(message)
        self._frame.adjustSize()
        self._place_frame()
        self._frame.raise_()
        self._frame.show()
        self._hide_timer.start(max(1500, int(duration_ms)))

    def _place_frame(self) -> None:
        if self._frame is None:
            return
        m = 14
        host = self._host
        w, h = self._frame.width(), self._frame.height()
        geo = host.rect()
        x = max(m, geo.width() - w - m)
        y = max(m, geo.height() - h - m)
        self._frame.move(x, y)

    def hide_immediately(self) -> None:
        self._hide_timer.stop()
        self._queue.clear()
        self._busy = False
        if self._frame is not None:
            self._frame.hide()

    def _hide(self) -> None:
        if self._frame is not None:
            self._frame.hide()
        self._busy = False
        if self._queue:
            self._show_next()
