from __future__ import annotations

import asyncio
import logging
import sys

from PyQt6.QtWidgets import QApplication

import qasync

def run_gui(*, symbol: str = "btc", interval: int = 5) -> None:
    """Start the Polymarket Analyzer desktop app (Qt + asyncio)."""
    from polymarket_analyzer.infra.env_config import load_app_env
    from polymarket_analyzer.ui.main_window import MainWindow

    load_app_env()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    app = QApplication(sys.argv)
    app.setApplicationName("Polymarket Analyzer")
    app.setOrganizationName("Polymarket Analyzer")
    from polymarket_analyzer.ui.ui_theme import apply_professional_app_style

    apply_professional_app_style(app)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    win = MainWindow(initial_symbol=symbol, initial_interval=interval)
    win.show()
    print("MainWindow shown")
    with loop:
        loop.run_forever()
