"""Polymarket Analyzer GUI entrypoint: ``python -m polymarket_analyzer.qt_main``."""

from __future__ import annotations

import argparse

from polymarket_analyzer.ui.run import run_gui


def main() -> None:
    p = argparse.ArgumentParser(description="Polymarket Analyzer — open the trading / chart window.")
    p.add_argument("--symbol", default="btc", help="Market symbol, e.g. btc, eth")
    p.add_argument("--interval", type=int, default=5, help="Interval minutes (1-60)")
    args = p.parse_args()
    run_gui(symbol=args.symbol, interval=max(1, min(60, int(args.interval))))


if __name__ == "__main__":
    main()
