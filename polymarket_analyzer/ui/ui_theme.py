"""Shared Qt stylesheet and Fusion baseline for a consistent desktop UI."""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

# Light, neutral trading-style palette; works with Fusion + QSS.
APP_STYLESHEET = """
QMainWindow {
    background-color: #e4e7ed;
}
QWidget#PmRoot {
    background-color: #e8eaef;
    color: #1c2330;
}
QScrollArea#PmScrollOuter {
    border: none;
    background-color: #e8eaef;
}
QScrollArea#PmScrollOuter > QWidget > QWidget {
    background-color: #e8eaef;
}
QScrollArea#PmSideScroll {
    border: none;
    background-color: #e8eaef;
}
QScrollArea#PmSideScroll > QWidget > QWidget {
    background-color: #e8eaef;
}
QScrollBar:vertical {
    width: 11px;
    margin: 2px 0 2px 0;
    border-radius: 5px;
    background: #dce0e8;
}
QScrollBar::handle:vertical {
    min-height: 28px;
    border-radius: 5px;
    background: #aeb8c8;
}
QScrollBar::handle:vertical:hover {
    background: #9aa6ba;
}
QScrollBar:horizontal {
    height: 11px;
    margin: 0 2px 0 2px;
    border-radius: 5px;
    background: #dce0e8;
}
QScrollBar::handle:horizontal {
    min-width: 28px;
    border-radius: 5px;
    background: #aeb8c8;
}
QScrollBar::handle:horizontal:hover {
    background: #9aa6ba;
}
QStatusBar {
    background-color: #f4f5f8;
    color: #3d4656;
    border-top: 1px solid #c8ced8;
    font-size: 11px;
    padding: 2px 8px;
}
QStatusBar::item {
    border: none;
}
QLabel#PmStatusSlug {
    color: #5c6575;
    font-size: 11px;
    padding: 2px 4px 2px 12px;
}
QToolTip {
    background-color: #1c2330;
    color: #f4f6f9;
    border: 1px solid #3d4656;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 11px;
}
QGroupBox {
    font-weight: 600;
    font-size: 11px;
    color: #1c2330;
    border: 1px solid #c4cad6;
    border-radius: 8px;
    margin-top: 16px;
    padding: 14px 16px 16px 16px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 2px;
    padding: 0 8px;
    color: #1a2332;
}
QLabel#PmTitle {
    font-size: 15px;
    font-weight: 700;
    color: #0f1419;
    letter-spacing: -0.01em;
}
QLabel#PmMuted {
    color: #5c6575;
    font-size: 11px;
}
QLabel#PmBody {
    color: #2c3340;
    font-size: 11px;
    line-height: 1.35;
}
QLabel#PmArbReadout {
    color: #2c3340;
    font-size: 10px;
    font-family: "Cascadia Mono", "Consolas", "SF Mono", "Liberation Mono", monospace;
    line-height: 1.4;
}
QLabel#PmMeta {
    color: #3d4656;
    font-size: 11px;
    font-weight: 500;
}
QLabel#PmSection {
    color: #4a5568;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    margin-top: 2px;
    margin-bottom: 2px;
}
QPushButton {
    padding: 8px 18px;
    min-height: 24px;
    border-radius: 6px;
    border: 1px solid #b8c0cc;
    background-color: #f4f6f9;
    color: #1c2330;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #e8ecf2;
    border-color: #a8b2c2;
}
QPushButton:pressed {
    background-color: #dde2ea;
}
QPushButton:disabled {
    color: #8b939e;
    background-color: #f0f1f4;
    border-color: #d5d9e0;
}
QPushButton#PmPrimaryButton {
    background-color: #1a5fb4;
    color: #ffffff;
    border: 1px solid #164a90;
    font-weight: 600;
}
QPushButton#PmPrimaryButton:hover {
    background-color: #1c6fd0;
    border-color: #164a90;
}
QPushButton#PmPrimaryButton:pressed {
    background-color: #154a94;
}
QPushButton#PmPrimaryButton:disabled {
    background-color: #a8c0e0;
    color: #e8eef8;
    border-color: #8fa8cc;
}
QPushButton#PmSecondaryButton {
    background-color: #ffffff;
    border: 1px solid #1a5fb4;
    color: #1a5fb4;
    font-weight: 600;
}
QPushButton#PmSecondaryButton:hover {
    background-color: #eef4fc;
}
QComboBox, QSpinBox, QDoubleSpinBox {
    padding: 5px 10px;
    min-height: 24px;
    border: 1px solid #b8c0cc;
    border-radius: 5px;
    background-color: #ffffff;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #8fa0b8;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #1a5fb4;
}
QCheckBox {
    spacing: 9px;
    font-size: 11px;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
}
QLineEdit {
    padding: 7px 11px;
    border: 1px solid #b8c0cc;
    border-radius: 5px;
    background-color: #fafbfc;
    color: #2c3340;
    selection-background-color: #1a5fb4;
}
QTableWidget {
    gridline-color: #e2e6ee;
    background-color: #ffffff;
    alternate-background-color: #f7f8fb;
    border: 1px solid #c4cad6;
    border-radius: 6px;
    font-size: 11px;
}
QTableWidget::item:selected {
    background-color: #cfe2f8;
    color: #0f1419;
}
QHeaderView::section {
    padding: 7px 9px;
    background-color: #eef1f6;
    color: #2c3340;
    border: none;
    border-bottom: 2px solid #b8c2d4;
    border-right: 1px solid #e2e6ee;
    font-weight: 600;
    font-size: 11px;
}
"""


def apply_professional_app_style(app: QApplication) -> None:
    """Fusion baseline + shared QSS for all analyzer windows."""
    app.setStyle("Fusion")
    base = QFont()
    base.setPointSize(10)
    app.setFont(base)
    app.setStyleSheet(APP_STYLESHEET)
