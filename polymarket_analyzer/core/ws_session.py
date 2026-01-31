from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable, Optional

import websockets

from polymarket_analyzer.core.models import BookLevelRow, BtcMarketSwitch, BtcOrderbookUpdate
from polymarket_analyzer.core.orderbook import OrderBook, as_float_from_json
from polymarket_analyzer.trading.arbitrage import quantize_arb_price

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

_log = logging.getLogger(__name__)

EmitUpdate = Callable[[BtcOrderbookUpdate], Awaitable[None]]
EmitSwitch = Callable[[BtcMarketSwitch], Awaitable[None]]


def now_ms() -> int:
    return int(time.time() * 1000)


def _synthetic_top_ask_row(best_ask: Optional[float]) -> list[BookLevelRow]:
    """
    When the socket sends ``best_bid_ask`` before a full ``book`` snapshot, ``top_rows_for_emit``
    can return an empty ask ladder while ``best_ask`` is valid. Expose a single level so the GUI
    can size BUY DOWN / BUY UP like a normal L2 top (capped at 5 shares later).
    """
    if best_ask is None or not (float(best_ask) > 0.0) or best_ask != best_ask:
        return []
    qa = quantize_arb_price(float(best_ask))
    if qa is None:
        return []
    return [BookLevelRow(price=f"{qa:.2f}", size="5.0000")]


def _rows_from_book(book: OrderBook) -> tuple[list[BookLevelRow], list[BookLevelRow], Optional[float], Optional[float], Optional[float]]:
    return book.top_rows_for_emit()


def _build_dual_update(
    slug: str,
    question: str,
    up_asset_id: str,
    down_asset_id: Optional[str],
    up_book: OrderBook,
    down_book: Optional[OrderBook],
) -> BtcOrderbookUpdate:
    u_bids, u_asks, u_bb, u_ba, u_mid = _rows_from_book(up_book)
    if down_book is not None:
        d_bids, d_asks, d_bb, d_ba, d_mid = _rows_from_book(down_book)
    else:
        d_bids, d_asks, d_bb, d_ba, d_mid = [], [], None, None, None
    return BtcOrderbookUpdate(
        slug=slug,
        question=question,
        asset_id=up_asset_id,
        down_asset_id=down_asset_id,
        best_bid=u_bb,
        best_ask=u_ba,
        mid=u_mid,
        bids=u_bids,
        asks=u_asks,
        updated_at_ms=now_ms(),
        down_best_bid=d_bb,
        down_best_ask=d_ba,
        down_mid=d_mid,
        down_bids=d_bids,
        down_asks=d_asks,
    )


async def emit_dual_ob_update(
    emit: EmitUpdate,
    slug: str,
    question: str,
    up_asset_id: str,
    down_asset_id: Optional[str],
    up_book: OrderBook,
    down_book: Optional[OrderBook],
    book_lock: asyncio.Lock,
) -> None:
    async with book_lock:
        msg = _build_dual_update(slug, question, up_asset_id, down_asset_id, up_book, down_book)
    await emit(msg)


async def emit_best_only_one_side(
    emit: EmitUpdate,
    slug: str,
    question: str,
    up_asset_id: str,
    down_asset_id: Optional[str],
    up_book: OrderBook,
    down_book: Optional[OrderBook],
    v: dict[str, Any],
    book_lock: asyncio.Lock,
) -> None:
    asset_id = v.get("asset_id")
    best_bid = as_float_from_json(v.get("best_bid")) if v.get("best_bid") is not None else None
    best_ask = as_float_from_json(v.get("best_ask")) if v.get("best_ask") is not None else None
    mid: Optional[float] = None
    if best_bid is not None and best_ask is not None and best_ask > 0.0 and best_bid > 0.0:
        mid = (best_ask + best_bid) / 2.0
    if not isinstance(asset_id, str):
        return

    msg: Optional[BtcOrderbookUpdate] = None
    async with book_lock:
        if asset_id == up_asset_id:
            empty = len(up_book.bids.levels) == 0 and len(up_book.asks.levels) == 0
            if not empty:
                return
        elif down_asset_id and asset_id == down_asset_id and down_book is not None:
            empty = len(down_book.bids.levels) == 0 and len(down_book.asks.levels) == 0
            if not empty:
                return
        else:
            return

        u_bids, u_asks, _, _, _ = _rows_from_book(up_book)
        if down_book is not None:
            d_bids, d_asks, d_bb, d_ba, d_mid = _rows_from_book(down_book)
        else:
            d_bids, d_asks, d_bb, d_ba, d_mid = [], [], None, None, None

        if asset_id == up_asset_id:
            if not u_asks:
                u_asks = list(_synthetic_top_ask_row(best_ask))
            msg = BtcOrderbookUpdate(
                slug=slug,
                question=question,
                asset_id=up_asset_id,
                down_asset_id=down_asset_id,
                best_bid=best_bid,
                best_ask=best_ask,
                mid=mid,
                bids=u_bids,
                asks=u_asks,
                updated_at_ms=now_ms(),
                down_best_bid=d_bb,
                down_best_ask=d_ba,
                down_mid=d_mid,
                down_bids=d_bids,
                down_asks=d_asks,
            )
        elif down_book is not None:
            u_bb = up_book.bids.best_price_desc()
            u_ba = up_book.asks.best_price_asc()
            u_mid = None
            if u_bb is not None and u_ba is not None and u_ba > 0 and u_bb > 0:
                u_mid = (u_ba + u_bb) / 2.0
            if not d_asks:
                d_asks = list(_synthetic_top_ask_row(best_ask))
            msg = BtcOrderbookUpdate(
                slug=slug,
                question=question,
                asset_id=up_asset_id,
                down_asset_id=down_asset_id,
                best_bid=u_bb,
                best_ask=u_ba,
                mid=u_mid,
                bids=u_bids,
                asks=u_asks,
                updated_at_ms=now_ms(),
                down_best_bid=best_bid,
                down_best_ask=best_ask,
                down_mid=mid,
                down_bids=d_bids,
                down_asks=d_asks,
            )

    if msg is not None:
        await emit(msg)


async def handle_ws_message(
    txt: str,
    slug: str,
    question: str,
    up_asset_id: str,
    down_asset_id: Optional[str],
    up_book: OrderBook,
    down_book: Optional[OrderBook],
    book_lock: asyncio.Lock,
    emit: EmitUpdate,
    emit_switch: EmitSwitch,
    session_cancel: asyncio.Event,
    symbol_lower: str,
    interval_minutes: int,
) -> None:
    if txt.strip() == "PONG":
        return
    try:
        parsed: Any = json.loads(txt)
    except json.JSONDecodeError:
        return

    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                await _handle_ws_dict(
                    item,
                    slug,
                    question,
                    up_asset_id,
                    down_asset_id,
                    up_book,
                    down_book,
                    book_lock,
                    emit,
                    emit_switch,
                    session_cancel,
                    symbol_lower,
                    interval_minutes,
                )
        return

    if isinstance(parsed, dict):
        await _handle_ws_dict(
            parsed,
            slug,
            question,
            up_asset_id,
            down_asset_id,
            up_book,
            down_book,
            book_lock,
            emit,
            emit_switch,
            session_cancel,
            symbol_lower,
            interval_minutes,
        )


def _book_for_asset(
    aid: str,
    up_asset_id: str,
    down_asset_id: Optional[str],
    up_book: OrderBook,
    down_book: Optional[OrderBook],
) -> Optional[OrderBook]:
    if aid == up_asset_id:
        return up_book
    if down_asset_id and aid == down_asset_id and down_book is not None:
        return down_book
    return None


async def _handle_ws_dict(
    v: dict[str, Any],
    slug: str,
    question: str,
    up_asset_id: str,
    down_asset_id: Optional[str],
    up_book: OrderBook,
    down_book: Optional[OrderBook],
    book_lock: asyncio.Lock,
    emit: EmitUpdate,
    emit_switch: EmitSwitch,
    session_cancel: asyncio.Event,
    symbol_lower: str,
    interval_minutes: int,
) -> None:
    event_type = str(v.get("event_type") or "")

    if event_type == "book":
        asset_id = v.get("asset_id")
        if not isinstance(asset_id, str):
            return
        ob = _book_for_asset(asset_id, up_asset_id, down_asset_id, up_book, down_book)
        if ob is None:
            return
        bids = v.get("bids")
        asks = v.get("asks")
        if not isinstance(bids, list) or not isinstance(asks, list):
            return
        async with book_lock:
            ob.bids.replace_from_book_array(bids)
            ob.asks.replace_from_book_array(asks)
        await emit_dual_ob_update(emit, slug, question, up_asset_id, down_asset_id, up_book, down_book, book_lock)

    elif event_type == "price_change":
        arr = v.get("price_changes")
        if not isinstance(arr, list):
            return
        touched = False
        async with book_lock:
            for ch in arr:
                if not isinstance(ch, dict):
                    continue
                aid = ch.get("asset_id")
                if not isinstance(aid, str):
                    continue
                ob = _book_for_asset(aid, up_asset_id, down_asset_id, up_book, down_book)
                if ob is None:
                    continue
                price = ch.get("price")
                if not isinstance(price, str):
                    continue
                size = as_float_from_json(ch.get("size")) if ch.get("size") is not None else 0.0
                side = str(ch.get("side") or "")
                if side == "BUY":
                    ob.bids.set_level(price, size or 0.0)
                elif side == "SELL":
                    ob.asks.set_level(price, size or 0.0)
                touched = True
        if touched:
            await emit_dual_ob_update(emit, slug, question, up_asset_id, down_asset_id, up_book, down_book, book_lock)

    elif event_type == "best_bid_ask":
        asset_id = v.get("asset_id")
        if not isinstance(asset_id, str):
            return
        ob = _book_for_asset(asset_id, up_asset_id, down_asset_id, up_book, down_book)
        if ob is None:
            return
        async with book_lock:
            empty = len(ob.bids.levels) == 0 and len(ob.asks.levels) == 0
        if empty:
            await emit_best_only_one_side(
                emit, slug, question, up_asset_id, down_asset_id, up_book, down_book, v, book_lock
            )

    elif event_type == "new_market":
        new_slug = v.get("slug")
        if not isinstance(new_slug, str) or new_slug == slug:
            return
        prefix = f"{symbol_lower}-updown-{interval_minutes}m-"
        if not new_slug.startswith(prefix):
            return
        active = bool(v.get("active", False))
        closed = bool(v.get("closed", False))
        if active and not closed:
            await emit_switch(
                BtcMarketSwitch(
                    from_slug=slug,
                    to_slug=new_slug,
                    reason="ws_new_market",
                )
            )
            session_cancel.set()


async def run_market_ws_session(
    slug: str,
    question: str,
    up_asset_id: str,
    down_asset_id: Optional[str],
    up_book: OrderBook,
    down_book: Optional[OrderBook],
    book_lock: asyncio.Lock,
    session_cancel: asyncio.Event,
    emit: EmitUpdate,
    emit_switch: EmitSwitch,
    symbol_lower: str,
    interval_minutes: int,
) -> None:
    assets = [up_asset_id]
    if down_asset_id and down_book is not None:
        assets.append(down_asset_id)
    sub = {
        "assets_ids": assets,
        "type": "market",
        "custom_feature_enabled": True,
    }

    try:
        async with websockets.connect(WS_URL) as ws:
            await ws.send(json.dumps(sub))

            async def ping_loop() -> None:
                try:
                    while not session_cancel.is_set():
                        await asyncio.sleep(10.0)
                        if session_cancel.is_set():
                            break
                        await ws.send("PING")
                except asyncio.CancelledError:
                    return

            ping_task = asyncio.create_task(ping_loop())

            try:
                while not session_cancel.is_set():
                    recv_task = asyncio.create_task(ws.recv())
                    wait_task = asyncio.create_task(session_cancel.wait())
                    recv_done, recv_pending = await asyncio.wait(
                        {recv_task, wait_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in recv_pending:
                        t.cancel()
                    await asyncio.gather(*recv_pending, return_exceptions=True)

                    if wait_task in recv_done:
                        break

                    try:
                        raw = recv_task.result()
                    except BaseException:
                        break
                    if isinstance(raw, str):
                        txt = raw
                    elif isinstance(raw, (bytes, bytearray)):
                        try:
                            txt = raw.decode()
                        except UnicodeDecodeError:
                            continue
                    else:
                        continue

                    await handle_ws_message(
                        txt,
                        slug,
                        question,
                        up_asset_id,
                        down_asset_id,
                        up_book,
                        down_book,
                        book_lock,
                        emit,
                        emit_switch,
                        session_cancel,
                        symbol_lower,
                        interval_minutes,
                    )
            finally:
                ping_task.cancel()
                try:
                    await ping_task
                except asyncio.CancelledError:
                    pass
                await ws.close()
    except Exception as e:
        session_cancel.set()
        _log.warning("market ws session ended: %s", e)
