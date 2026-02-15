"""
On-chain trading preflight for Polymarket CLOB: validate signer / funder by ``signature_type``,
check pUSD + conditional-token approvals, and submit missing approvals.

- ``signature_type == 0`` (EOA): approvals are sent from the EOA (MATIC/POL for gas).
- ``signature_type == 2`` (Gnosis Safe): approvals execute via Polymarket relayer; requires
  builder API credentials and a funder address equal to the CREATE2-derived Safe for the EOA.
- ``signature_type == 1`` (POLY_PROXY): with an explicit ``PM_FUNDER``, it must be a deployed
  contract (non-empty code) and not the bare EOA. If ``PM_FUNDER`` is omitted, the Polymarket
  CREATE2 Safe for this key is used (same as type 2). Relayer approvals apply only when the
  trading vault equals that Safe; other proxies need manual approval on polymarket.com.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, List, Optional, Sequence, Tuple

from web3 import Web3
from web3.types import TxReceipt

# Polygon addresses from ``py_clob_client_v2.config`` (CLOB V2 exchanges + pUSD collateral).
_RELAYER_URL = "https://relayer-v2.polymarket.com/"
_CHAIN_ID = 137

_MAX_UINT = 2**256 - 1
# Rough minimum collateral (6 decimals) allowance to consider "already approved" for trading.
_MIN_USDC_ALLOWANCE = 10**12

_ERC20_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]

_ERC1155_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "operator", "type": "address"},
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"},
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "type": "function",
    },
]


@dataclass
class AllowanceReport:
    """Collateral (pUSD) + CTF approval flags for standard and neg-risk V2 exchanges."""

    owner: str
    usdc_exchange: bool
    usdc_neg_risk: bool
    ctf_exchange: bool
    ctf_neg_risk: bool

    @property
    def all_ok(self) -> bool:
        return self.usdc_exchange and self.usdc_neg_risk and self.ctf_exchange and self.ctf_neg_risk


@dataclass
class TradingContext:
    signature_type: int
    eoa: str
    """Address that holds collateral / CTF for CLOB (funder / Safe / EOA)."""

    trading_address: str


def _normalize_hex_pk(private_key: str) -> str:
    s = private_key.strip().replace(" ", "").replace("\n", "")
    if s.startswith("0x") or s.startswith("0X"):
        s = s[2:]
    if not re.fullmatch(r"[0-9a-fA-F]{64}", s):
        raise ValueError("private key must be 64 hex characters (optionally prefixed with 0x)")
    return "0x" + s.lower()


def eoa_checksum_address(private_key: str) -> str:
    """Return checksummed EOA address for a hex private key (no RPC)."""
    pk = _normalize_hex_pk(private_key)
    acct = Web3().eth.account.from_key(pk)
    return Web3.to_checksum_address(acct.address)


def _clob_polygon_configs() -> Tuple[Any, Any]:
    from py_clob_client_v2.config import get_contract_config

    cfg = get_contract_config(_CHAIN_ID)
    std = SimpleNamespace(
        collateral=cfg.collateral,
        conditional_tokens=cfg.conditional_tokens,
        exchange=cfg.exchange_v2,
    )
    neg = SimpleNamespace(exchange=cfg.neg_risk_exchange_v2)
    return std, neg


def _derived_safe_address(eoa: str) -> str:
    from py_builder_relayer_client.builder.derive import derive
    from py_builder_relayer_client.config import get_contract_config as relay_factory_config

    cfg = relay_factory_config(_CHAIN_ID)
    return derive(Web3.to_checksum_address(eoa), cfg.safe_factory)


def derived_safe_funder_address(private_key: str) -> str:
    """
    Polymarket CREATE2 Gnosis Safe on Polygon (chain id 137) for this private key.

    This is the default ``PM_FUNDER`` when using signature types 1 or 2 and the env var is unset.
    """
    return _derived_safe_address(eoa_checksum_address(private_key))


def make_web3(rpc_url: Optional[str] = None) -> Web3:
    url = (rpc_url or "").strip() or "https://polygon-bor-rpc.publicnode.com"
    w3 = Web3(Web3.HTTPProvider(url))
    if not w3.is_connected():
        raise RuntimeError(f"could not connect to Polygon RPC: {url}")
    return w3


def resolve_trading_context(
    *,
    private_key: str,
    funder: Optional[str],
    signature_type: int,
    w3: Web3,
) -> TradingContext:
    """
    Resolve EOA from ``private_key`` and validate ``funder`` / on-chain shape for ``signature_type``.

    - Type 0: trading address is the EOA; ``funder`` if set must match the EOA.
    - Type 1: if ``funder`` is omitted, the CREATE2 Polymarket Safe for this key is used. If set,
      it must not be the EOA; an explicit funder must have contract code on Polygon (undeployed
      Safe is only allowed when using the auto-derived address).
    - Type 2: if ``funder`` is omitted, the CREATE2 Safe is used; if set, it must match that address.
    """
    pk = _normalize_hex_pk(private_key)
    acct = w3.eth.account.from_key(pk)
    eoa = Web3.to_checksum_address(acct.address)

    ft_raw = (funder or "").strip()
    if signature_type == 0:
        if ft_raw:
            ft = Web3.to_checksum_address(ft_raw)
            if ft != eoa:
                raise ValueError(
                    f"PM_SIG_TYPE=0 (EOA): PM_FUNDER must match the signer address {eoa}, got {ft}."
                )
            trading = ft
        else:
            trading = eoa
        return TradingContext(signature_type=0, eoa=eoa, trading_address=trading)

    if signature_type not in (1, 2):
        raise ValueError(f"unsupported signature type: {signature_type} (expected 0, 1, or 2)")

    expected_safe = _derived_safe_address(eoa)
    funder_explicit = bool(ft_raw)
    if funder_explicit:
        trading = Web3.to_checksum_address(ft_raw)
    else:
        trading = expected_safe

    if signature_type == 2:
        if trading != expected_safe:
            raise ValueError(
                f"PM_SIG_TYPE=2 (Gnosis Safe): PM_FUNDER must be the relayer Safe for this key.\n"
                f"Expected (CREATE2): {expected_safe}\n"
                f"Got: {trading}"
            )
        return TradingContext(signature_type=2, eoa=eoa, trading_address=trading)

    # signature_type == 1 — POLY_PROXY
    if trading == eoa:
        raise ValueError("PM_SIG_TYPE=1 (POLY_PROXY): PM_FUNDER must not equal the EOA signer address.")
    if funder_explicit:
        code = w3.eth.get_code(trading)
        if not code or code == b"\x00":
            raise ValueError(
                f"PM_SIG_TYPE=1 (POLY_PROXY): explicit PM_FUNDER {trading} has no contract code on Polygon — "
                "expected a deployed proxy / contract wallet, or omit PM_FUNDER to use the auto-derived Safe."
            )
    return TradingContext(signature_type=1, eoa=eoa, trading_address=trading)


def check_allowances(w3: Web3, owner: str) -> AllowanceReport:
    std, neg = _clob_polygon_configs()
    owner_c = Web3.to_checksum_address(owner)
    collateral = Web3.to_checksum_address(std.collateral)
    ctf = Web3.to_checksum_address(std.conditional_tokens)
    ex = Web3.to_checksum_address(std.exchange)
    ex_n = Web3.to_checksum_address(neg.exchange)

    erc20 = w3.eth.contract(address=collateral, abi=_ERC20_ABI)
    c = w3.eth.contract(address=ctf, abi=_ERC1155_ABI)

    u_ex = int(erc20.functions.allowance(owner_c, ex).call()) >= _MIN_USDC_ALLOWANCE
    u_nr = int(erc20.functions.allowance(owner_c, ex_n).call()) >= _MIN_USDC_ALLOWANCE
    c_ex = bool(c.functions.isApprovedForAll(owner_c, ex).call())
    c_nr = bool(c.functions.isApprovedForAll(owner_c, ex_n).call())

    return AllowanceReport(
        owner=owner_c,
        usdc_exchange=u_ex,
        usdc_neg_risk=u_nr,
        ctf_exchange=c_ex,
        ctf_neg_risk=c_nr,
    )


def _encode_approve(w3: Web3, token: str, spender: str) -> str:
    c = w3.eth.contract(address=Web3.to_checksum_address(token), abi=_ERC20_ABI)
    return c.encode_abi("approve", [Web3.to_checksum_address(spender), _MAX_UINT])


def _encode_set_approval_all(w3: Web3, ctf: str, operator: str, approved: bool) -> str:
    c = w3.eth.contract(address=Web3.to_checksum_address(ctf), abi=_ERC1155_ABI)
    return c.encode_abi("setApprovalForAll", [Web3.to_checksum_address(operator), approved])


def _missing_approval_txs(w3: Web3, rep: AllowanceReport) -> List[Tuple[str, str]]:
    """Returns list of (to, data) for still-required approvals."""
    std, neg = _clob_polygon_configs()
    collateral = Web3.to_checksum_address(std.collateral)
    ctf = Web3.to_checksum_address(std.conditional_tokens)
    ex = Web3.to_checksum_address(std.exchange)
    ex_n = Web3.to_checksum_address(neg.exchange)

    out: List[Tuple[str, str]] = []
    if not rep.usdc_exchange:
        out.append((collateral, _encode_approve(w3, collateral, ex)))
    if not rep.usdc_neg_risk:
        out.append((collateral, _encode_approve(w3, collateral, ex_n)))
    if not rep.ctf_exchange:
        out.append((ctf, _encode_set_approval_all(w3, ctf, ex, True)))
    if not rep.ctf_neg_risk:
        out.append((ctf, _encode_set_approval_all(w3, ctf, ex_n, True)))
    return out


def _min_gas_balance_wei() -> int:
    return Web3.to_wei(0.005, "ether")


def _send_eoa_approvals(w3: Web3, private_key: str, txs: Sequence[Tuple[str, str]]) -> List[str]:
    if not txs:
        return []
    pk = _normalize_hex_pk(private_key)
    acct = w3.eth.account.from_key(pk)
    addr = Web3.to_checksum_address(acct.address)
    if w3.eth.get_balance(addr) < _min_gas_balance_wei():
        raise RuntimeError(
            "Low POL/MATIC balance for gas on Polygon (need roughly >= 0.005 POL). Fund the EOA and retry."
        )
    hashes: List[str] = []
    nonce = w3.eth.get_transaction_count(addr, "pending")
    chain_id = w3.eth.chain_id
    for to_addr, data in txs:
        tx: dict[str, Any] = {
            "from": addr,
            "to": Web3.to_checksum_address(to_addr),
            "data": data,
            "value": 0,
            "nonce": nonce,
            "chainId": chain_id,
        }
        gas = w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas * 1.2) + 10_000
        gp = w3.eth.gas_price
        tx["gasPrice"] = gp
        signed = acct.sign_transaction(tx)
        raw = signed.raw_transaction if hasattr(signed, "raw_transaction") else signed.rawTransaction
        h = w3.eth.send_raw_transaction(raw)
        hashes.append(h.to_0x_hex())
        rc: TxReceipt = w3.eth.wait_for_transaction_receipt(h, timeout=600)
        if rc.get("status") != 1:
            raise RuntimeError(f"approval tx reverted: {h.to_0x_hex()}")
        nonce += 1
    return hashes


def _relay_client(private_key: str, builder_key: str, builder_secret: str, builder_passphrase: str):
    from py_builder_relayer_client.client import RelayClient
    from py_builder_signing_sdk.config import BuilderConfig
    from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds

    creds = BuilderApiKeyCreds(key=builder_key, secret=builder_secret, passphrase=builder_passphrase)
    bc = BuilderConfig(local_builder_creds=creds)
    return RelayClient(_RELAYER_URL, _CHAIN_ID, _normalize_hex_pk(private_key), bc)


def _ensure_safe_deployed(relay) -> None:
    safe = relay.get_expected_safe()
    if relay.get_deployed(safe):
        return
    resp = relay.deploy()
    mined = resp.wait()
    if not mined:
        raise RuntimeError("Safe deployment via relayer failed or timed out.")


def _execute_relayer_approvals(
    relay,
    w3: Web3,
    rep: AllowanceReport,
) -> Tuple[Optional[str], Optional[str]]:
    from py_builder_relayer_client.models import OperationType, SafeTransaction

    txs_plain = _missing_approval_txs(w3, rep)
    if not txs_plain:
        return None, None
    safe_txs = [
        SafeTransaction(
            to=Web3.to_checksum_address(to),
            operation=OperationType.Call,
            data=data,
            value="0",
        )
        for to, data in txs_plain
    ]
    resp = relay.execute(safe_txs, "polymarket_analyzer:approvals")
    mined = resp.wait()
    if not mined:
        raise RuntimeError("approval batch via relayer failed or timed out.")
    return resp.transaction_id, resp.transaction_hash


def preflight_allowances(
    *,
    private_key: str,
    funder: Optional[str],
    signature_type: int,
    rpc_url: Optional[str] = None,
) -> dict:
    """
    Read-only: resolve trading address for ``signature_type`` and return current allowance flags.
    """
    w3 = make_web3(rpc_url)
    ctx = resolve_trading_context(private_key=private_key, funder=funder, signature_type=signature_type, w3=w3)
    rep = check_allowances(w3, ctx.trading_address)
    return {
        "trading_address": ctx.trading_address,
        "eoa": ctx.eoa,
        "signature_type": ctx.signature_type,
        "allowances": {
            "usdc_exchange": rep.usdc_exchange,
            "usdc_neg_risk": rep.usdc_neg_risk,
            "ctf_exchange": rep.ctf_exchange,
            "ctf_neg_risk": rep.ctf_neg_risk,
        },
        "all_ok": rep.all_ok,
    }


def ensure_trading_approvals(
    *,
    private_key: str,
    funder: Optional[str],
    signature_type: int,
    rpc_url: Optional[str] = None,
    builder_key: Optional[str] = None,
    builder_secret: Optional[str] = None,
    builder_passphrase: Optional[str] = None,
) -> dict:
    """
    Validate context, check allowances on the trading address, and submit any missing approvals.

    Returns a dict with keys: ``trading_address``, ``eoa``, ``signature_type``, ``allowances`` (dict),
    ``already_sufficient`` (bool), ``tx_hashes`` (EOA), ``relayer_transaction_id``, ``relayer_transaction_hash``.
    """
    w3 = make_web3(rpc_url)
    ctx = resolve_trading_context(private_key=private_key, funder=funder, signature_type=signature_type, w3=w3)
    rep = check_allowances(w3, ctx.trading_address)
    allowance_dict = {
        "usdc_exchange": rep.usdc_exchange,
        "usdc_neg_risk": rep.usdc_neg_risk,
        "ctf_exchange": rep.ctf_exchange,
        "ctf_neg_risk": rep.ctf_neg_risk,
    }
    base: dict = {
        "trading_address": ctx.trading_address,
        "eoa": ctx.eoa,
        "signature_type": ctx.signature_type,
        "allowances": allowance_dict,
        "already_sufficient": rep.all_ok,
        "tx_hashes": [],
        "relayer_transaction_id": None,
        "relayer_transaction_hash": None,
    }
    if rep.all_ok:
        return base

    pending = _missing_approval_txs(w3, rep)
    if ctx.signature_type == 0:
        base["tx_hashes"] = _send_eoa_approvals(w3, private_key, pending)
        base["already_sufficient"] = check_allowances(w3, ctx.trading_address).all_ok
        return base

    expected_safe = _derived_safe_address(ctx.eoa)
    trading_c = Web3.to_checksum_address(ctx.trading_address)
    use_relayer = trading_c == expected_safe

    if ctx.signature_type == 1 and not use_relayer:
        raise ValueError(
            f"PM_SIG_TYPE=1 (POLY_PROXY): funder {trading_c} is not the deterministic Polymarket Safe "
            f"for this private key ({expected_safe}). Allowances are insufficient for trading, but "
            "this app cannot submit approval txs for arbitrary proxy contracts (no relayer PROXY mode "
            "in Python). Approve USDC + conditional tokens on polymarket.com, or use PM_SIG_TYPE=2 "
            "with PM_FUNDER set to your Safe if applicable."
        )

    # Relayer path: signature type 2, or type 1 when funder is the derived Safe.
    if not builder_key or not builder_secret or not builder_passphrase:
        raise ValueError(
            "Builder API credentials are required for Safe/proxy relayer approvals. "
            "Set PM_BUILDER_KEY, PM_BUILDER_SECRET, PM_BUILDER_PASSPHRASE (or SQLite pm_builder_*)."
        )
    relay = _relay_client(private_key, builder_key, builder_secret, builder_passphrase)
    if trading_c != relay.get_expected_safe():
        raise ValueError("internal error: trading address does not match relayer expected Safe.")
    _ensure_safe_deployed(relay)
    tid, th = _execute_relayer_approvals(relay, w3, rep)
    base["relayer_transaction_id"] = tid
    base["relayer_transaction_hash"] = th
    base["already_sufficient"] = check_allowances(w3, ctx.trading_address).all_ok
    return base


def approvals_dependencies_available() -> bool:
    """True if ``web3`` and ``py_clob_client_v2`` are installed (Polygon contract addresses)."""
    try:
        import web3  # noqa: F401
        from py_clob_client_v2.config import get_contract_config  # noqa: F401

        _ = get_contract_config(137, False)
        return True
    except Exception:
        return False
