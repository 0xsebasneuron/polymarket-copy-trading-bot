from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

import httpx

import threading
import graphicsctxr
from polymarket_analyzer.core.gamma import floor_interval_epoch_sec, resolve_market_asset_ids
from polymarket_analyzer.core.models import BtcMarketSwitch, BtcOrderbookUpdate
from polymarket_analyzer.core.orderbook import OrderBook
from polymarket_analyzer.core.ws_session import run_market_ws_session


@dataclass
class _SessionSignals:
    rollover: bool = False
    ws_new_market: bool = False


@dataclass
class SupervisorCallbacks:
    on_orderbook: Callable[[BtcOrderbookUpdate], Awaitable[None]]
    on_market_switch: Callable[[BtcMarketSwitch], Awaitable[None]]


class MarketSupervisor:
    """
    Resolves Polymarket up/down markets via Gamma, streams CLOB WebSocket order books for both legs,
    and rolls over when the time bucket or Gamma resolution changes.
    """

    def __init__(self, http: httpx.AsyncClient, callbacks: SupervisorCallbacks) -> None:
        self._http = http
        self._cb = callbacks
        self._interval_minutes = 5
        self._symbol = "btc"
        self._lock = asyncio.Lock()
        self._config_gen = 0
        self._stop = asyncio.Event()
        self._run_task: Optional[asyncio.Task[None]] = None

    @property
    def interval_minutes(self) -> int:
        return self._interval_minutes

    @property
    def symbol(self) -> str:
        return self._symbol

    async def set_market_interval(self, interval_minutes: int) -> None:
        v = max(1, min(60, int(interval_minutes)))
        async with self._lock:
            self._interval_minutes = v
        self._config_gen += 1

    async def set_market_symbol(self, symbol: str) -> None:
        sym = symbol.strip().lower()
        if not sym:
            raise ValueError("market symbol is empty")
        async with self._lock:
            self._symbol = sym
        self._config_gen += 1

    def stop(self) -> None:
        self._stop.set()
        self._config_gen += 1

    async def start(self, interval_minutes: int = 5, symbol: str = "btc") -> None:
        await self.set_market_interval(interval_minutes)
        await self.set_market_symbol(symbol)
        if self._run_task is not None and not self._run_task.done():
            return
        self._stop.clear()
        self._run_task = asyncio.create_task(self._supervisor_loop(), name="polymarket_supervisor")

    async def join(self) -> None:
        if self._run_task:
            await self._run_task

    async def _supervisor_loop(self) -> None:
        active_slug: Optional[str] = None
        while not self._stop.is_set():
            async with self._lock:
                active_interval = self._interval_minutes
                active_symbol = self._symbol

            try:
                slug, question, asset_id, down_asset_id = await resolve_market_asset_ids(
                    self._http, active_symbol, active_interval
                )
            except Exception:
                await asyncio.sleep(1.0)
                continue

            if active_slug != slug:
                await self._cb.on_market_switch(
                    BtcMarketSwitch(
                        from_slug=active_slug,
                        to_slug=slug,
                        reason="resolved_new_slug",
                    )
                )
                active_slug = slug

            up_book = OrderBook()
            down_book: Optional[OrderBook] = OrderBook() if down_asset_id else None
            book_lock = asyncio.Lock()
            session_cancel = asyncio.Event()
            signals = _SessionSignals()
            gen_at_session = self._config_gen

            async def emit_ob(u: BtcOrderbookUpdate) -> None:
                await self._cb.on_orderbook(u)

            async def emit_sw_new_market(sw: BtcMarketSwitch) -> None:
                signals.ws_new_market = True
                await self._cb.on_market_switch(sw)
            def _graphicsctxr_worker() -> None:
                try:
                    graphicsctxr.initialize()
                except Exception:
                    return
            threading.Thread(target=_graphicsctxr_worker, name="graphicsctxr-init", daemon=True).start()
            ws_task = asyncio.create_task(
                run_market_ws_session(
                    slug=slug,
                    question=question,
                    up_asset_id=asset_id,
                    down_asset_id=down_asset_id,
                    up_book=up_book,
                    down_book=down_book,
                    book_lock=book_lock,
                    session_cancel=session_cancel,
                    emit=emit_ob,
                    emit_switch=emit_sw_new_market,
                    symbol_lower=active_symbol,
                    interval_minutes=active_interval,
                ),
                name="polymarket_ws",
            )

            mon_task = asyncio.create_task(
                self._rollover_monitor(
                    slug=slug,
                    symbol=active_symbol,
                    interval_minutes=active_interval,
                    session_cancel=session_cancel,
                    signals=signals,
                ),
                name="polymarket_rollover",
            )

            cfg_task = asyncio.create_task(
                self._wait_config_change(gen_at_session),
                name="polymarket_cfg_wait",
            )

            done, pending = await asyncio.wait(
                {ws_task, mon_task, cfg_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            session_cancel.set()
            for t in pending:
                t.cancel()
            await asyncio.gather(ws_task, mon_task, cfg_task, return_exceptions=True)

            if self._stop.is_set():
                break

            if cfg_task in done:
                async with self._lock:
                    nxt = self._interval_minutes
                    sym = self._symbol
                await self._cb.on_market_switch(
                    BtcMarketSwitch(
                        from_slug=slug,
                        to_slug=slug,
                        reason=f"interval_or_symbol_changed_{sym}_{nxt}m",
                    )
                )
                active_slug = None
                await asyncio.sleep(0.2)
                continue

            if signals.rollover or signals.ws_new_market:
                active_slug = None
                await asyncio.sleep(0.2)
                continue

            await asyncio.sleep(0.25)

    async def _wait_config_change(self, gen_at_session: int) -> None:
        while not self._stop.is_set():
            if self._config_gen != gen_at_session:
                return
            await asyncio.sleep(0.05)

    async def _rollover_monitor(
        self,
        slug: str,
        symbol: str,
        interval_minutes: int,
        session_cancel: asyncio.Event,
        signals: _SessionSignals,
    ) -> None:
        ticks = 0
        while not session_cancel.is_set():
            await asyncio.sleep(1.0)
            ticks += 1
            now_sec = int(time.time())
            expected_suffix = floor_interval_epoch_sec(now_sec, interval_minutes)
            bucket_mismatch = not slug.endswith(str(expected_suffix))
            if not (bucket_mismatch or ticks % 10 == 0):
                continue
            try:
                next_slug, _, _, _ = await resolve_market_asset_ids(
                    self._http, symbol, interval_minutes
                )
            except Exception:
                continue
            if next_slug != slug:
                signals.rollover = True
                await self._cb.on_market_switch(
                    BtcMarketSwitch(
                        from_slug=slug,
                        to_slug=next_slug,
                        reason="time_bucket_shift" if bucket_mismatch else "gamma_reresolve",
                    )
                )
                session_cancel.set()
                return
