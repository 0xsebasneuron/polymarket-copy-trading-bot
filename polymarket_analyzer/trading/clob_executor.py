"""
Post CLOB orders using ``py-clob-client-v2`` (Polymarket **CLOB V2**; sync client via ``asyncio.to_thread``).

Requires: ``pip install py-clob-client-v2`` for **live** posts. Legacy ``py-clob-client`` (V1) orders are rejected
on production with ``order_version_mismatch``. With ``simulate=True``, no orders are sent (real prices still come
from the GUI / caller).

Store secrets via SQLite helpers or the GUI Rust parity keys:
``pm_private_key``, optional ``pm_sig_type`` (``0`` / ``1`` / ``2``), optional ``pm_funder`` (vault override only),
optional ``pm_builder_*`` for relayer approvals.
"""


from __future__ import annotations



import asyncio
import time

from typing import Any, Dict, Tuple





def clob_client_available() -> bool:

    try:

        import py_clob_client_v2.client  # noqa: F401



        return True

    except ImportError:

        return False





def _bundle_order_type_label() -> str:

    try:

        from py_clob_client_v2.clob_types import OrderType  # noqa: F401



        return "FAK" if hasattr(OrderType, "FAK") else "FOK"

    except Exception:

        return "FAK"





def _simulated_leg(

    *,

    host: str,

    chain_id: int,

    side: str,

    leg: str,

    token_id: str,

    price: float,

    size: float,

    order_type: str,

    funder: str,

    signature_type: int,

) -> Dict[str, Any]:

    return {

        "simulated": True,

        "host": host,

        "chain_id": chain_id,

        "side": side,

        "leg": leg,

        "token_id": token_id,

        "price": float(price),

        "size": float(size),

        "order_type": order_type,

        "funder": funder,

        "signature_type": int(signature_type),

        "post_order": "skipped",

    }





async def buy_yes_no_bundle_fak(

    *,

    host: str,

    chain_id: int,

    private_key: str,

    funder: str,

    signature_type: int,

    up_token_id: str,

    down_token_id: str,

    up_price: float,

    down_price: float,

    size: float,

    simulate: bool = False,

    inter_leg_delay_sec: float = 0.0,

) -> Tuple[Any, Any]:

    """
    BUY bundle: UP token + DOWN token at the given limits (FAK, or FOK if FAK is unavailable).

    Both legs are posted in one call, in order, on the same client — not atomic on-chain; partial fills need manual handling.

    ``inter_leg_delay_sec``: optional pause **between** UP and DOWN ``post_order`` (live: blocking sleep in worker thread;
    sim: ``asyncio.sleep``). Same **share size** on both legs.

    If ``simulate`` is True, returns leg dicts only (no ``post_order``).
    """

    ot = _bundle_order_type_label()

    if simulate:

        leg_up = _simulated_leg(

                host=host,

                chain_id=chain_id,

                side="BUY",

                leg="UP",

                token_id=up_token_id,

                price=up_price,

                size=size,

                order_type=ot,

                funder=funder,

                signature_type=signature_type,

            )

        dly = max(0.0, float(inter_leg_delay_sec))

        if dly > 0.0:

            await asyncio.sleep(dly)

        leg_dn = _simulated_leg(

                host=host,

                chain_id=chain_id,

                side="BUY",

                leg="DOWN",

                token_id=down_token_id,

                price=down_price,

                size=size,

                order_type=ot,

                funder=funder,

                signature_type=signature_type,

            )

        return (leg_up, leg_dn)



    def _sync() -> Tuple[Any, Any]:

        from py_clob_client_v2.client import ClobClient

        from py_clob_client_v2.clob_types import OrderArgs, OrderType

        from py_clob_client_v2.order_builder.constants import BUY



        client = ClobClient(
            host=host,
            chain_id=chain_id,
            key=private_key,
            signature_type=signature_type,
            funder=funder,
        )

        client.set_api_creds(client.create_or_derive_api_key())



        order_t = OrderType.FAK

        if not hasattr(OrderType, "FAK"):

            order_t = OrderType.FOK



        o_up = client.create_order(

            OrderArgs(token_id=up_token_id, price=float(up_price), size=float(size), side=BUY)

        )

        r_up = client.post_order(o_up, order_t)

        dly = max(0.0, float(inter_leg_delay_sec))

        if dly > 0.0:

            time.sleep(dly)

        o_dn = client.create_order(

            OrderArgs(token_id=down_token_id, price=float(down_price), size=float(size), side=BUY)

        )

        r_dn = client.post_order(o_dn, order_t)

        return r_up, r_dn



    return await asyncio.to_thread(_sync)


async def buy_single_leg_fak(
    *,
    host: str,
    chain_id: int,
    private_key: str,
    funder: str,
    signature_type: int,
    leg: str,
    token_id: str,
    price: float,
    size: float,
    simulate: bool = False,
) -> Any:
    """
    Single BUY on one outcome token (FAK, or FOK if FAK is unavailable).
    ``leg`` is only metadata in the simulated response (UP vs DOWN).
    """
    leg_u = "UP" if str(leg).strip().upper() == "UP" else "DOWN"
    ot = _bundle_order_type_label()
    if simulate:
        return _simulated_leg(
            host=host,
            chain_id=chain_id,
            side="BUY",
            leg=leg_u,
            token_id=token_id,
            price=price,
            size=size,
            order_type=ot,
            funder=funder,
            signature_type=signature_type,
        )

    def _sync() -> Any:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import OrderArgs, OrderType
        from py_clob_client_v2.order_builder.constants import BUY

        client = ClobClient(
            host=host,
            chain_id=chain_id,
            key=private_key,
            signature_type=signature_type,
            funder=funder,
        )
        client.set_api_creds(client.create_or_derive_api_key())
        order_t = OrderType.FAK
        if not hasattr(OrderType, "FAK"):
            order_t = OrderType.FOK
        o = client.create_order(
            OrderArgs(token_id=token_id, price=float(price), size=float(size), side=BUY)
        )
        return client.post_order(o, order_t)

    return await asyncio.to_thread(_sync)


async def sell_yes_no_bundle_fak(

    *,

    host: str,

    chain_id: int,

    private_key: str,

    funder: str,

    signature_type: int,

    up_token_id: str,

    down_token_id: str,

    up_price: float,

    down_price: float,

    size: float,

    simulate: bool = False,

) -> Tuple[Any, Any]:

    """Two SELL legs at top-of-book bid prices (requires inventory on both outcomes)."""



    ot = _bundle_order_type_label()

    if simulate:

        return (

            _simulated_leg(

                host=host,

                chain_id=chain_id,

                side="SELL",

                leg="UP",

                token_id=up_token_id,

                price=up_price,

                size=size,

                order_type=ot,

                funder=funder,

                signature_type=signature_type,

            ),

            _simulated_leg(

                host=host,

                chain_id=chain_id,

                side="SELL",

                leg="DOWN",

                token_id=down_token_id,

                price=down_price,

                size=size,

                order_type=ot,

                funder=funder,

                signature_type=signature_type,

            ),

        )



    def _sync() -> Tuple[Any, Any]:

        from py_clob_client_v2.client import ClobClient

        from py_clob_client_v2.clob_types import OrderArgs, OrderType

        from py_clob_client_v2.order_builder.constants import SELL



        client = ClobClient(
            host=host,
            chain_id=chain_id,
            key=private_key,
            signature_type=signature_type,
            funder=funder,
        )

        client.set_api_creds(client.create_or_derive_api_key())



        order_t = OrderType.FAK

        if not hasattr(OrderType, "FAK"):

            order_t = OrderType.FOK



        o_up = client.create_order(

            OrderArgs(token_id=up_token_id, price=float(up_price), size=float(size), side=SELL)

        )

        r_up = client.post_order(o_up, order_t)

        o_dn = client.create_order(

            OrderArgs(token_id=down_token_id, price=float(down_price), size=float(size), side=SELL)

        )

        r_dn = client.post_order(o_dn, order_t)

        return r_up, r_dn



    return await asyncio.to_thread(_sync)


