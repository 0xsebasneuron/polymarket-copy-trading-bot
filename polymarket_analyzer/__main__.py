"""
Polymarket Analyzer — run the app from the command line: GUI, NDJSON stream, or SQLite helpers.
Examples: ``python -m polymarket_analyzer --gui`` or ``python -m polymarket_analyzer.qt_main``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

import httpx

from polymarket_analyzer.core.models import BtcMarketSwitch, BtcOrderbookUpdate
from polymarket_analyzer.infra.sqlite_store import (
    sqlite_delete_secret,
    sqlite_get_path_str,
    sqlite_load_secret,
    sqlite_save_secret,
)
from polymarket_analyzer.core.supervisor import MarketSupervisor, SupervisorCallbacks


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


async def _amain() -> int:
    p = argparse.ArgumentParser(
        description="Polymarket Analyzer — live Polymarket CLOB books (NDJSON) or desktop GUI (--gui)."
    )
    p.add_argument("--symbol", default="btc", help="Market symbol prefix, e.g. btc, eth, sol, xrp")
    p.add_argument("--interval", type=int, default=5, help="Interval minutes (1–60)")
    p.add_argument("--sqlite-path", action="store_true", help="Print resolved SQLite DB path and exit")
    p.add_argument("--sqlite-save", nargs=2, metavar=("KEY", "VALUE"), help="Save secret to local SQLite store")
    p.add_argument("--sqlite-load", metavar="KEY", help="Load secret from local SQLite store")
    p.add_argument("--sqlite-delete", metavar="KEY", help="Delete secret from local SQLite store")
    p.add_argument("-q", "--quiet", action="store_true", help="Less logging")
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        metavar="SEC",
        help="Stop after this many seconds (default: run until interrupted)",
    )
    p.add_argument(
        "--gui",
        action="store_true",
        help="Open PyQt window instead of streaming NDJSON (requires PyQt6 and qasync)",
    )
    args = p.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.gui:
        from polymarket_analyzer.ui.run import run_gui

        interval = max(1, min(60, int(args.interval)))
        symbol = str(args.symbol).strip().lower() or "btc"
        run_gui(symbol=symbol, interval=interval)
        return 0

    if args.sqlite_path:
        _emit({"kind": "sqlitePath", "path": sqlite_get_path_str()})
        return 0

    if args.sqlite_save:
        k, v = args.sqlite_save
        sqlite_save_secret(k, v)
        _emit({"kind": "sqliteSecretSaved", "key": k})
        return 0

    if args.sqlite_load:
        v = sqlite_load_secret(args.sqlite_load)
        _emit({"kind": "sqliteSecretLoad", "key": args.sqlite_load, "value": v})
        return 0

    if args.sqlite_delete:
        sqlite_delete_secret(args.sqlite_delete)
        _emit({"kind": "sqliteSecretDeleted", "key": args.sqlite_delete})
        return 0

    interval = max(1, min(60, int(args.interval)))
    symbol = str(args.symbol).strip().lower()

    async def on_orderbook(u: BtcOrderbookUpdate) -> None:
        d = u.to_camel_dict()
        d["kind"] = "btcOrderbookUpdate"
        _emit(d)

    async def on_switch(sw: BtcMarketSwitch) -> None:
        d = sw.to_camel_dict()
        d["kind"] = "btcMarketSwitch"
        _emit(d)

    callbacks = SupervisorCallbacks(on_orderbook=on_orderbook, on_market_switch=on_switch)

    async with httpx.AsyncClient(
        headers={"user-agent": "polymarket-analyzer-python/0.1"},
        timeout=httpx.Timeout(30.0),
    ) as client:
        sup = MarketSupervisor(client, callbacks)
        await sup.start(interval_minutes=interval, symbol=symbol)
        join_task = asyncio.create_task(sup.join(), name="join_supervisor")
        try:
            if args.duration is not None:
                _, pending = await asyncio.wait(
                    {join_task},
                    timeout=max(0.1, float(args.duration)),
                )
                if join_task in pending:
                    sup.stop()
            await join_task
        except asyncio.CancelledError:
            sup.stop()
            if not join_task.done():
                join_task.cancel()
                try:
                    await join_task
                except asyncio.CancelledError:
                    pass
        finally:
            if not join_task.done():
                sup.stop()
                try:
                    await join_task
                except Exception:
                    join_task.cancel()
                    try:
                        await join_task
                    except asyncio.CancelledError:
                        pass
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(_amain()))
    except KeyboardInterrupt:
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
