from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime
from typing import Any, Optional

import httpx
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QResizeEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from polymarket_analyzer.trading.arbitrage import (
    buy_bundle_opportunity_at_asks,
    cross_time_min_ask_sum_vs_par,
    quantize_arb_price,
)
from polymarket_analyzer.trading.cross_time_strategy import pair_swing_summary
from polymarket_analyzer.trading.leg_sequence import rise_bps_vs_window_min, staggered_hedge_order
from polymarket_analyzer.trading.clob_executor import buy_single_leg_fak, clob_client_available
from polymarket_analyzer.core.models import BtcMarketSwitch, BtcOrderbookUpdate
from polymarket_analyzer.infra.env_config import (
    builder_key_from_env,
    builder_passphrase_from_env,
    builder_secret_from_env,
    funder_from_env,
    funder_resolve_for_clob,
    private_key_from_env,
    rpc_url_from_env,
    sig_type_resolve,
    simulate_clob_orders_forced_by_env,
    simulate_clob_orders_resolve,
)
from polymarket_analyzer.infra.sqlite_store import sqlite_get_path_str, sqlite_load_secret, sqlite_save_secret
from polymarket_analyzer.core.supervisor import MarketSupervisor, SupervisorCallbacks
from polymarket_analyzer.trading.trading_summary import (
    cumulative_pnl_by_mode,
    format_clob_response_cell,
    session_leg_shares_for_slug,
    single_leg_buy_cost,
)
from polymarket_analyzer.ui.mid_chart import MidPriceChart
from polymarket_analyzer.ui.toast import ToastManager
from polymarket_analyzer.chain.wallet_balance import fetch_wallet_snapshot, format_wallet_snapshot_line

_log = logging.getLogger(__name__)

# Staggered two-leg automation: minimum seconds after a completed pair before another may start (Pair CD spinbox floor).
PAIR_STAGGER_COOLDOWN_MIN_S = 5

# Auto BUY to balance: default |UP−DOWN| trigger (shares), max shares per balance FAK, imbalance spinbox arrow step.
KEEP_BALANCE_IMBALANCE_DEFAULT_SH = 10.0
KEEP_BALANCE_CLIP_MAX_SH = 3.0
KEEP_BALANCE_IMBALANCE_SPIN_STEP_SH = 3.0


def _fmt_prob(x: Optional[float]) -> str:
    if x is None or (isinstance(x, float) and (x != x)):  # NaN
        return "—"
    return f"{x:.4f}"


def _fmt_cents(price_str: str) -> str:
    try:
        n = float(price_str)
    except ValueError:
        return "—"
    if not (n == n):
        return "—"
    return f"{round(n * 100)}¢"


def _fmt_ts_ms(ms: int) -> str:
    """Local wall time for cross-time diagnostic labels."""
    return datetime.fromtimestamp(ms / 1000.0).strftime("%H:%M:%S")


class OrderBookBridge(QObject):
    """Marshals supervisor callbacks onto Qt signals (same thread with qasync)."""

    orderbook = pyqtSignal(object)
    market_switch = pyqtSignal(object)


class MainWindow(QMainWindow):
    def __init__(self, *, initial_symbol: str = "btc", initial_interval: int = 5) -> None:
        super().__init__()
        self.setWindowTitle("Polymarket Analyzer — Books & CLOB")
        self.resize(1240, 960)
        self.setMinimumSize(1024, 720)

        self._bridge = OrderBookBridge()
        self._bridge.orderbook.connect(self._on_orderbook, Qt.ConnectionType.QueuedConnection)
        self._bridge.market_switch.connect(self._on_market_switch, Qt.ConnectionType.QueuedConnection)

        self._http: Optional[httpx.AsyncClient] = None
        self._supervisor: Optional[MarketSupervisor] = None
        self._closing = False
        self._initial_symbol = initial_symbol.strip().lower() or "btc"
        self._initial_interval = max(1, min(60, int(initial_interval)))
        self._chart_slug: Optional[str] = None
        self._last_u: Optional[BtcOrderbookUpdate] = None
        self._trade_history: list[dict[str, Any]] = []
        self._approvals_inflight: bool = False
        self._clob_trade_inflight: bool = False
        self._balance_scheduled: bool = False
        self._balance_last_fire: float = -1.0
        self._up_ask_hist: deque[tuple[int, float]] = deque(maxlen=6000)
        self._dn_ask_hist: deque[tuple[int, float]] = deque(maxlen=6000)
        self._pair_gross_hist: deque[tuple[int, float]] = deque(maxlen=8000)
        self._seq_stagger_armed: bool = True
        self._seq_stagger_scheduled: bool = False
        self._seq_stagger_inflight: bool = False
        self._seq_stagger_cd_until: float = 0.0
        self._toast = ToastManager(self)
        self._wallet_timer = QTimer(self)
        self._wallet_timer.setInterval(60_000)
        self._wallet_timer.timeout.connect(lambda: asyncio.ensure_future(self._refresh_wallet_balance()))

        central = QWidget()
        central.setObjectName("PmRoot")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 14, 16, 18)
        outer.setSpacing(12)

        # --- Top tier: wallet | market & quotes ---
        wallet_box = QGroupBox("Wallet")
        w_lo = QVBoxLayout(wallet_box)
        w_lo.setSpacing(8)
        self._wallet_lbl = QLabel(
            "Wallet: set PM_PRIVATE_KEY and PM_RPC_URL (optional; default public RPC) — click Refresh"
        )
        self._wallet_lbl.setObjectName("PmBody")
        self._wallet_lbl.setWordWrap(True)
        self._wallet_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._btn_wallet_refresh = QPushButton("Refresh wallet")
        self._btn_wallet_refresh.setObjectName("PmSecondaryButton")
        self._btn_wallet_refresh.setToolTip("Fetch EOA POL (gas) and pUSD vault balance via Polygon RPC.")
        self._btn_wallet_refresh.clicked.connect(lambda: asyncio.ensure_future(self._refresh_wallet_balance()))
        w_row = QHBoxLayout()
        w_row.addWidget(self._wallet_lbl, stretch=1)
        w_row.addWidget(self._btn_wallet_refresh)
        w_lo.addLayout(w_row)

        status_box = QGroupBox("Market & quotes")
        s_lo = QVBoxLayout(status_box)
        s_lo.setSpacing(6)
        self._switch_lbl = QLabel("")
        self._switch_lbl.setObjectName("PmMuted")
        self._switch_lbl.setWordWrap(True)
        s_lo.addWidget(self._switch_lbl)
        self._title_lbl = QLabel("—")
        self._title_lbl.setObjectName("PmTitle")
        self._title_lbl.setWordWrap(True)
        s_lo.addWidget(self._title_lbl)
        self._slug_lbl = QLabel("")
        self._slug_lbl.setObjectName("PmMuted")
        self._slug_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        s_lo.addWidget(self._slug_lbl)
        self._mid_lbl = QLabel("Mid: —")
        self._bb_lbl = QLabel("Best bid: —")
        self._ba_lbl = QLabel("Best ask: —")
        for w in (self._bb_lbl, self._ba_lbl, self._mid_lbl):
            w.setObjectName("PmMeta")
        m_up = QHBoxLayout()
        m_up.setSpacing(12)
        m_up.addWidget(self._bb_lbl)
        m_up.addWidget(self._ba_lbl)
        m_up.addWidget(self._mid_lbl)
        m_up.addStretch()
        s_lo.addLayout(m_up)
        self._bb_dn_lbl = QLabel("DOWN bid: —")
        self._ba_dn_lbl = QLabel("DOWN ask: —")
        self._mid_dn_lbl = QLabel("DOWN mid: —")
        for w in (self._bb_dn_lbl, self._ba_dn_lbl, self._mid_dn_lbl):
            w.setObjectName("PmMeta")
        m_dn = QHBoxLayout()
        m_dn.setSpacing(12)
        m_dn.addWidget(self._bb_dn_lbl)
        m_dn.addWidget(self._ba_dn_lbl)
        m_dn.addWidget(self._mid_dn_lbl)
        m_dn.addStretch()
        s_lo.addLayout(m_dn)

        outer.addWidget(wallet_box)
        outer.addWidget(status_box)

        # --- Order book tables (shared by sections below) ---
        self._asks = QTableWidget(0, 3)
        self._asks.setHorizontalHeaderLabels(["Price", "¢", "Size"])
        self._asks.horizontalHeader().setStretchLastSection(True)
        self._bids = QTableWidget(0, 3)
        self._bids.setHorizontalHeaderLabels(["Price", "¢", "Size"])
        self._bids.horizontalHeader().setStretchLastSection(True)
        self._asks_dn = QTableWidget(0, 3)
        self._asks_dn.setHorizontalHeaderLabels(["Price", "¢", "Size"])
        self._asks_dn.horizontalHeader().setStretchLastSection(True)
        self._bids_dn = QTableWidget(0, 3)
        self._bids_dn.setHorizontalHeaderLabels(["Price", "¢", "Size"])
        self._bids_dn.horizontalHeader().setStretchLastSection(True)
        for tw in (self._asks, self._bids, self._asks_dn, self._bids_dn):
            tw.setShowGrid(True)
            tw.setAlternatingRowColors(True)
            tw.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            tw.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            tw.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            tw.verticalHeader().setVisible(False)
            tw.verticalHeader().setDefaultSectionSize(22)
            tw.setMinimumHeight(100)
            tw.setMaximumHeight(240)

        # --- Main column: execution + UP books, chart, CLOB + DOWN books (vertical) ---
        left_scroll = QScrollArea()
        left_scroll.setObjectName("PmSideScroll")
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_inner = QWidget()
        left_scroll.setWidget(left_inner)
        lv = QVBoxLayout(left_inner)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(10)

        ctrl = QGroupBox("Execution")
        cfl = QVBoxLayout(ctrl)
        cfl.setSpacing(8)
        row_sym = QHBoxLayout()
        row_sym.addWidget(QLabel("Symbol:"))
        self._symbol = QComboBox()
        self._symbol.setEditable(True)
        for s in ("btc", "eth", "sol", "xrp"):
            self._symbol.addItem(s.upper(), s)
        self._set_combo_symbol(self._initial_symbol)
        row_sym.addWidget(self._symbol, stretch=1)
        cfl.addLayout(row_sym)
        row_iv = QHBoxLayout()
        row_iv.addWidget(QLabel("Interval (min):"))
        self._interval = QSpinBox()
        self._interval.setRange(1, 60)
        self._interval.setValue(self._initial_interval)
        row_iv.addWidget(self._interval)
        row_iv.addStretch()
        cfl.addLayout(row_iv)
        self._apply = QPushButton("Apply")
        self._apply.setObjectName("PmPrimaryButton")
        self._apply.clicked.connect(lambda: asyncio.ensure_future(self._apply_settings()))
        cfl.addWidget(self._apply)
        lv.addWidget(ctrl)

        self._btn_buy_up = QPushButton("BUY UP @ ask (FAK)")
        self._btn_buy_up.setObjectName("PmPrimaryButton")
        self._btn_buy_up.setToolTip(
            "Single CLOB BUY on the UP outcome token at **current** best ask (py-clob-client-v2). "
            "Set PM_PRIVATE_KEY and PM_SIG_TYPE in .env or SQLite. Does not post the DOWN leg."
        )
        self._btn_buy_up.setEnabled(False)
        self._btn_buy_up.clicked.connect(
            lambda: asyncio.ensure_future(self._execute_single_leg_impl("UP", show_result_dialog=True))
        )
        lv.addWidget(self._btn_buy_up)
        self._btn_buy_dn = QPushButton("BUY DOWN @ ask (FAK)")
        self._btn_buy_dn.setObjectName("PmPrimaryButton")
        self._btn_buy_dn.setToolTip(
            "Single CLOB BUY on the DOWN outcome token at **current** best ask. Does not post the UP leg."
        )
        self._btn_buy_dn.setEnabled(False)
        self._btn_buy_dn.clicked.connect(
            lambda: asyncio.ensure_future(self._execute_single_leg_impl("DOWN", show_result_dialog=True))
        )
        lv.addWidget(self._btn_buy_dn)
        self._btn_approvals = QPushButton("Check / set trading approvals")
        self._btn_approvals.setObjectName("PmSecondaryButton")
        self._btn_approvals.setToolTip(
            "Validate PM_SIG_TYPE vs EOA / proxy / Safe, read allowances on Polygon, then submit "
            "missing USDC + CTF approvals (EOA gas or Polymarket relayer). Needs web3; relayer path "
            "needs PM_BUILDER_* (see .env.example)."
        )
        try:
            from polymarket_analyzer.chain.approvals import approvals_dependencies_available

            self._btn_approvals.setEnabled(approvals_dependencies_available())
        except Exception:
            self._btn_approvals.setEnabled(False)
        self._btn_approvals.clicked.connect(lambda: asyncio.ensure_future(self._on_check_set_approvals()))
        lv.addWidget(self._btn_approvals)

        self._sim_env_force = simulate_clob_orders_forced_by_env()
        self._cb_sim = QCheckBox("Simulate CLOB orders (live prices, no post_order)")
        self._cb_sim.setToolTip(
            "Uses real WebSocket books for sizing and prices; skips Polymarket CLOB post_order. "
            "Set PM_SIMULATE=1 in .env to force on, or toggle here (saved as SQLite pm_simulate)."
        )
        self._cb_sim.blockSignals(True)
        self._cb_sim.setChecked(simulate_clob_orders_resolve(sqlite_load_secret("pm_simulate")))
        if self._sim_env_force:
            self._cb_sim.setChecked(True)
            self._cb_sim.setEnabled(False)
            self._cb_sim.setToolTip("PM_SIMULATE is set in the environment — CLOB execution stays simulated.")
        self._cb_sim.blockSignals(False)
        self._cb_sim.toggled.connect(self._on_simulate_clob_toggled)
        self._cb_sim.stateChanged.connect(lambda _: self._refresh_arb_label())
        lv.addWidget(self._cb_sim)

        for text, table in (
            ("UP — asks (sell)", self._asks),
            ("UP — bids (buy)", self._bids),
        ):
            cap = QLabel(text)
            cap.setObjectName("PmSection")
            lv.addWidget(cap)
            lv.addWidget(table)

        self._mid_chart = MidPriceChart(interval_minutes=self._initial_interval)
        self._mid_chart.setMinimumHeight(360)
        self._mid_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart_box = QGroupBox("Chart: UP price = mid, DOWN price = 1 − mid — X = full market window")
        chart_box.setMinimumHeight(400)
        chart_lo = QVBoxLayout(chart_box)
        chart_lo.setContentsMargins(4, 8, 4, 8)
        chart_lo.setSpacing(4)
        chart_lo.addWidget(self._mid_chart, stretch=1)
        chart_center = QWidget()
        chart_center.setMinimumHeight(400)
        cv = QVBoxLayout(chart_center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        cv.addWidget(chart_box, stretch=1)

        right_scroll = QScrollArea()
        right_scroll.setObjectName("PmSideScroll")
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_inner = QWidget()
        right_scroll.setWidget(right_inner)
        rv = QVBoxLayout(right_inner)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(10)

        arb_box = QGroupBox("CLOB — cross-time & automation")
        arb_lo = QVBoxLayout(arb_box)
        arb_lo.setSpacing(10)
        row_fee = QHBoxLayout()
        row_fee.setSpacing(8)
        row_fee.addWidget(QLabel("Assumed fee"))
        self._fee_bps = QSpinBox()
        self._fee_bps.setRange(0, 200)
        self._fee_bps.setSingleStep(1)
        self._fee_bps.setValue(0)
        self._fee_bps.setSuffix(" bps / leg")
        self._fee_bps.valueChanged.connect(self._refresh_arb_label)
        row_fee.addWidget(self._fee_bps)
        row_fee.addStretch()
        row_fee.addWidget(QLabel("Cross-time"))
        self._sb_cross_win = QSpinBox()
        self._sb_cross_win.setRange(5, 600)
        self._sb_cross_win.setSingleStep(1)
        self._sb_cross_win.setValue(120)
        self._sb_cross_win.setSuffix(" s")
        self._sb_cross_win.setToolTip(
            "Look back this many seconds for the **minimum** UP best ask (at some time t1) and "
            "**minimum** DOWN best ask (at some time t2). Their sum can be < $1 even when each "
            "snapshot’s paired asks are ≥ $1. Execute posts **one** BUY at the **current** best ask "
            "for UP or DOWN — not the historic t1/t2 quotes."
        )
        self._sb_cross_win.valueChanged.connect(self._refresh_arb_label)
        row_fee.addWidget(self._sb_cross_win)
        arb_lo.addLayout(row_fee)

        row3 = QHBoxLayout()
        row3.setSpacing(8)
        self._cb_keep_balance = QCheckBox("Auto BUY to balance UP vs DOWN (session log, this market)")
        self._cb_keep_balance.setToolTip(
            "Sums single-leg BUY rows in the Trading log for the **current** market slug (SIM and REAL). "
            "When |UP shares − DOWN shares| ≥ threshold, posts **one** FAK on the lagging leg, size up to "
            f"{KEEP_BALANCE_CLIP_MAX_SH:g} sh per order (not more than the imbalance). "
            "Uses **current** best ask only. Cooldown limits rate."
        )
        self._cb_keep_balance.blockSignals(True)
        bal_on = (sqlite_load_secret("pm_keep_balance") or "").strip().lower() in ("1", "true", "yes", "on")
        self._cb_keep_balance.setChecked(bal_on)
        self._cb_keep_balance.blockSignals(False)
        self._cb_keep_balance.toggled.connect(self._on_keep_balance_toggled)
        row3.addWidget(self._cb_keep_balance)
        row3.addWidget(QLabel("Cooldown"))
        self._sb_balance_cd = QSpinBox()
        self._sb_balance_cd.setRange(3, 600)
        self._sb_balance_cd.setSingleStep(1)
        self._sb_balance_cd.setValue(15)
        self._sb_balance_cd.setSuffix(" s")
        row3.addWidget(self._sb_balance_cd)
        row3.addWidget(QLabel("Imbalance ≥"))
        self._dsp_balance_threshold = QDoubleSpinBox()
        self._dsp_balance_threshold.setRange(0.01, 50.0)
        self._dsp_balance_threshold.setDecimals(2)
        self._dsp_balance_threshold.setSingleStep(KEEP_BALANCE_IMBALANCE_SPIN_STEP_SH)
        self._dsp_balance_threshold.setValue(KEEP_BALANCE_IMBALANCE_DEFAULT_SH)
        self._dsp_balance_threshold.setSuffix(" sh")
        self._dsp_balance_threshold.setToolTip(
            "Trigger a balance BUY when session UP total and DOWN total for this slug differ by at least this many shares. "
            f"Spinner step ±{KEEP_BALANCE_IMBALANCE_SPIN_STEP_SH:g} sh."
        )
        row3.addWidget(self._dsp_balance_threshold)
        row3.addStretch()
        arb_lo.addLayout(row3)
        self._sb_balance_cd.valueChanged.connect(lambda _: self._consider_keep_balance())
        self._dsp_balance_threshold.valueChanged.connect(lambda _: self._consider_keep_balance())

        row3b = QVBoxLayout()
        self._cb_rise_stagger = QCheckBox(
            "Auto: rising best-ask leg → BUY that leg, then the other leg (staggered)"
        )
        self._cb_rise_stagger.setToolTip(
            "Uses the **Cross-time window** (seconds) on each leg’s best ask history. "
            "If UP ask rose enough vs its window low → BUY UP, wait, then BUY DOWN. "
            "If DOWN rose enough (and more than UP when both qualify) → BUY DOWN first, then UP. "
            "Requires a dip below the rise threshold before the next trigger. Respects Simulate / keys. "
            f"**Pair CD** (cooldown after a finished two-leg run) cannot be set below {PAIR_STAGGER_COOLDOWN_MIN_S} s."
        )
        row3b.addWidget(self._cb_rise_stagger)
        row3b_ctrl = QHBoxLayout()
        row3b_ctrl.setSpacing(6)
        row3b_ctrl.addWidget(QLabel("Min rise"))
        self._sb_rise_stagger_min = QSpinBox()
        self._sb_rise_stagger_min.setRange(5, 500)
        self._sb_rise_stagger_min.setSingleStep(1)
        self._sb_rise_stagger_min.setValue(25)
        self._sb_rise_stagger_min.setSuffix(" bps")
        row3b_ctrl.addWidget(self._sb_rise_stagger_min)
        row3b_ctrl.addWidget(QLabel("2nd leg"))
        self._dsp_rise_stagger_delay = QDoubleSpinBox()
        self._dsp_rise_stagger_delay.setRange(0.01, 120.0)
        self._dsp_rise_stagger_delay.setDecimals(2)
        self._dsp_rise_stagger_delay.setSingleStep(0.01)
        self._dsp_rise_stagger_delay.setValue(2.0)
        self._dsp_rise_stagger_delay.setSuffix(" s")
        row3b_ctrl.addWidget(self._dsp_rise_stagger_delay)
        row3b_ctrl.addWidget(QLabel("Pair CD"))
        self._sb_rise_stagger_cd = QSpinBox()
        self._sb_rise_stagger_cd.setRange(PAIR_STAGGER_COOLDOWN_MIN_S, 900)
        self._sb_rise_stagger_cd.setSingleStep(1)
        self._sb_rise_stagger_cd.setValue(60)
        self._sb_rise_stagger_cd.setSuffix(" s")
        self._sb_rise_stagger_cd.setToolTip(
            f"Wait at least this long after a completed staggered pair before the next two-leg sequence. "
            f"Minimum {PAIR_STAGGER_COOLDOWN_MIN_S} s."
        )
        row3b_ctrl.addWidget(self._sb_rise_stagger_cd)
        row3b_ctrl.addStretch()
        row3b.addLayout(row3b_ctrl)
        arb_lo.addLayout(row3b)

        self._arb_lbl = QLabel("Waiting for dual-leg book…")
        self._arb_lbl.setObjectName("PmArbReadout")
        self._arb_lbl.setWordWrap(True)
        arb_lo.addWidget(self._arb_lbl)
        rv.addWidget(arb_box)

        swing_box = QGroupBox("Pair-gross swing — rise → pullback (cheap) → recovery (playbook text)")
        swing_lo = QVBoxLayout(swing_box)
        swing_lo.setSpacing(8)
        swing_row = QHBoxLayout()
        swing_row.setSpacing(8)
        swing_row.addWidget(QLabel("Min rise"))
        self._sb_swing_rise = QSpinBox()
        self._sb_swing_rise.setRange(5, 500)
        self._sb_swing_rise.setSingleStep(1)
        self._sb_swing_rise.setValue(30)
        self._sb_swing_rise.setSuffix(" bps")
        swing_row.addWidget(self._sb_swing_rise)
        swing_row.addWidget(QLabel("Pullback"))
        self._sb_swing_pull = QSpinBox()
        self._sb_swing_pull.setRange(5, 300)
        self._sb_swing_pull.setSingleStep(1)
        self._sb_swing_pull.setValue(25)
        self._sb_swing_pull.setSuffix(" bps")
        swing_row.addWidget(self._sb_swing_pull)
        swing_row.addWidget(QLabel("Recovery"))
        self._sb_swing_rec = QSpinBox()
        self._sb_swing_rec.setRange(5, 300)
        self._sb_swing_rec.setSingleStep(1)
        self._sb_swing_rec.setValue(20)
        self._sb_swing_rec.setSuffix(" bps")
        swing_row.addWidget(self._sb_swing_rec)
        swing_row.addStretch()
        for s in (self._sb_swing_rise, self._sb_swing_pull, self._sb_swing_rec):
            s.valueChanged.connect(self._refresh_arb_label)
        swing_lo.addLayout(swing_row)
        self._swing_hint_lbl = QLabel("")
        self._swing_hint_lbl.setObjectName("PmMuted")
        self._swing_hint_lbl.setWordWrap(True)
        swing_lo.addWidget(self._swing_hint_lbl)
        rv.addWidget(swing_box)

        for text, table in (
            ("DOWN — asks (sell)", self._asks_dn),
            ("DOWN — bids (buy)", self._bids_dn),
        ):
            cap = QLabel(text)
            cap.setObjectName("PmSection")
            rv.addWidget(cap)
            rv.addWidget(table)

        left_scroll.setMinimumHeight(200)
        right_scroll.setMinimumHeight(220)
        for panel in (left_scroll, right_scroll):
            panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        chart_center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

        outer.addWidget(chart_center, 1)
        outer.addWidget(left_scroll, 0)
        outer.addWidget(right_scroll, 0)

        log_box = QGroupBox(
            "Trading log — sim + real (PnL column 0 for single-leg rows; pair PnL needs both legs logged)"
        )
        log_lo = QVBoxLayout(log_box)
        log_lo.setSpacing(8)
        self._trade_table = QTableWidget(0, 11)
        self._trade_table.setHorizontalHeaderLabels(
            ["Time", "Mode", "Market", "Shares", "UP@", "DOWN@", "Cost $", "Fee $", "PnL $", "UP resp.", "DOWN resp."]
        )
        self._trade_table.setAlternatingRowColors(True)
        self._trade_table.setMinimumHeight(160)
        self._trade_table.setMaximumHeight(280)
        self._trade_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._trade_table.setShowGrid(True)
        self._trade_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._trade_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._trade_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._trade_table.verticalHeader().setVisible(False)
        self._trade_table.verticalHeader().setDefaultSectionSize(24)
        self._trade_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._trade_table.horizontalHeader().setStretchLastSection(True)
        log_lo.addWidget(self._trade_table)
        self._trade_pnl_lbl = QLabel(
            "Session cumulative (est. @ $1 / pair resolution; single-leg rows use PnL $0) — Sim: $0.0000 | Real: $0.0000"
        )
        self._trade_pnl_lbl.setObjectName("PmBody")
        self._trade_pnl_lbl.setWordWrap(True)
        log_lo.addWidget(self._trade_pnl_lbl)
        outer.addWidget(log_box)

        db_box = QGroupBox("Local SQLite")
        db_l = QFormLayout(db_box)
        db_l.setSpacing(10)
        path = sqlite_get_path_str()
        pe = QLineEdit(path)
        pe.setReadOnly(True)
        db_l.addRow("DB path:", pe)
        keys_lbl = QLabel(
            ".env: PM_PRIVATE_KEY, PM_SIG_TYPE, optional PM_SIMULATE, PM_RPC_URL, PM_BUILDER_* — or SQLite "
            "pm_* / pm_builder_* / pm_simulate / pm_keep_balance (optional pm_funder if vault differs from auto-derived address)"
        )
        keys_lbl.setObjectName("PmMuted")
        keys_lbl.setWordWrap(True)
        db_l.addRow("CLOB keys:", keys_lbl)
        outer.addWidget(db_box)

        central.setMinimumWidth(720)

        page_scroll = QScrollArea()
        page_scroll.setObjectName("PmScrollOuter")
        page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        page_scroll.setWidgetResizable(True)
        page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        page_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        page_scroll.setWidget(central)
        self.setCentralWidget(page_scroll)

        sb = QStatusBar(self)
        sb.setSizeGripEnabled(True)
        self.setStatusBar(sb)
        self._status_slug_lbl = QLabel("—")
        self._status_slug_lbl.setObjectName("PmStatusSlug")
        sb.addPermanentWidget(self._status_slug_lbl, 0)
        sb.showMessage("Starting market supervisor…", 0)

        asyncio.ensure_future(self._bootstrap())

    def _toast_msg(self, text: str, *, kind: str = "info", duration_ms: int = 5000) -> None:
        self._toast.schedule(text, kind=kind, duration_ms=duration_ms)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._toast.reposition_if_visible()

    async def _refresh_wallet_balance(self) -> None:
        pk = private_key_from_env() or sqlite_load_secret("pm_private_key")
        rpc = rpc_url_from_env()
        st = sig_type_resolve(sqlite_load_secret("pm_sig_type"))
        fr = funder_from_env() or sqlite_load_secret("pm_funder")

        def _run():
            return fetch_wallet_snapshot(
                private_key=(str(pk).strip() if pk else None),
                rpc_url=rpc,
                signature_type=st,
                funder_explicit=(str(fr).strip() if fr else None),
            )

        try:
            snap = await asyncio.to_thread(_run)
        except Exception as e:
            self._wallet_lbl.setText(f"Wallet: refresh error — {e}")
            self._toast_msg(f"Wallet refresh failed: {e}", kind="error", duration_ms=7000)
            return
        self._wallet_lbl.setText(format_wallet_snapshot_line(snap))
        if snap.error:
            self._toast_msg(f"Wallet: {snap.error}", kind="warn", duration_ms=7000)
        else:
            self._toast_msg("Wallet balances updated.", kind="info", duration_ms=2800)

    def _on_simulate_clob_toggled(self, checked: bool) -> None:
        if getattr(self, "_sim_env_force", False):
            return
        try:
            sqlite_save_secret("pm_simulate", "1" if checked else "0")
        except Exception:
            pass
        self._toast_msg(
            f"Simulate CLOB orders: {'ON' if checked else 'OFF'} (saved to SQLite when possible).",
            kind="info",
            duration_ms=3500,
        )

    def _set_combo_symbol(self, sym_lower: str) -> None:
        sym_lower = sym_lower.strip().lower()
        for i in range(self._symbol.count()):
            if self._symbol.itemData(i) == sym_lower:
                self._symbol.setCurrentIndex(i)
                return
        self._symbol.setCurrentText(sym_lower.upper())

    def _read_symbol(self) -> str:
        data = self._symbol.currentData()
        if isinstance(data, str) and data:
            return data.strip().lower()
        return self._symbol.currentText().strip().lower()

    async def _bootstrap(self) -> None:
        try:
            self._http = httpx.AsyncClient(
                headers={"user-agent": "polymarket-analyzer-python/0.1 (PyQt)"},
                timeout=httpx.Timeout(30.0),
            )

            async def on_orderbook(u: BtcOrderbookUpdate) -> None:
                self._bridge.orderbook.emit(u)

            async def on_switch(sw: BtcMarketSwitch) -> None:
                self._bridge.market_switch.emit(sw)

            self._supervisor = MarketSupervisor(
                self._http,
                SupervisorCallbacks(on_orderbook=on_orderbook, on_market_switch=on_switch),
            )
            await self._supervisor.start(
                interval_minutes=self._interval.value(),
                symbol=self._read_symbol() or self._initial_symbol,
            )
        except Exception as e:
            def _startup_failed() -> None:
                QMessageBox.critical(self, "Startup failed", str(e))
                app = QApplication.instance()
                if app is not None:
                    app.quit()

            QTimer.singleShot(0, _startup_failed)
        else:
            asyncio.ensure_future(self._refresh_wallet_balance())
            self._wallet_timer.start()

            def _online_status() -> None:
                sb = self.statusBar()
                if sb is not None:
                    sb.showMessage("Supervisor online · Polymarket WebSocket feed", 0)

            QTimer.singleShot(0, _online_status)

    async def _apply_settings(self) -> None:
        if not self._supervisor:
            return
        sym = self._read_symbol()
        if not sym:
            self._toast_msg("Symbol: enter a non-empty symbol.", kind="warn", duration_ms=5000)
            return
        try:
            await self._supervisor.set_market_interval(self._interval.value())
            await self._supervisor.set_market_symbol(sym)
            self._mid_chart.set_fallback_interval_minutes(self._interval.value())
        except Exception as e:
            self._toast_msg(f"Apply failed: {e}", kind="error", duration_ms=8000)
            return
        self._toast_msg(f"Market applied: {sym.upper()} @ {self._interval.value()} min.", kind="info", duration_ms=4000)
        sb = self.statusBar()
        if sb is not None:
            sb.showMessage(f"Market set · {sym.upper()} · {self._interval.value()} min interval", 0)

    def _on_market_switch(self, sw: object) -> None:
        if not isinstance(sw, BtcMarketSwitch):
            return
        self._switch_lbl.setText(
            f"Market switch: {sw.from_slug or '—'} → {sw.to_slug} ({sw.reason})"
        )
        self._status_slug_lbl.setText((sw.to_slug or "—")[:96])
        if sw.from_slug is not None and sw.from_slug != sw.to_slug:
            self._chart_slug = None
            self._mid_chart.clear_series()
            self._up_ask_hist.clear()
            self._dn_ask_hist.clear()
            self._pair_gross_hist.clear()
            self._seq_stagger_armed = True
            self._seq_stagger_cd_until = 0.0
            sb = self.statusBar()
            if sb is not None:
                sb.showMessage("Market bucket changed · refreshing chart & histories", 0)

    def _on_orderbook(self, u: object) -> None:
        if not isinstance(u, BtcOrderbookUpdate):
            return
        if self._chart_slug != u.slug:
            self._chart_slug = u.slug
            self._mid_chart.clear_series()
            self._up_ask_hist.clear()
            self._dn_ask_hist.clear()
            self._pair_gross_hist.clear()
            self._seq_stagger_armed = True
            self._seq_stagger_cd_until = 0.0
        self._mid_chart.add_mid(u.updated_at_ms, u.mid, u.slug)

        self._title_lbl.setText(u.question or "—")
        self._slug_lbl.setText(u.slug)
        self._mid_lbl.setText(f"UP mid: {_fmt_prob(u.mid)}")
        self._bb_lbl.setText(f"UP bid: {_fmt_prob(u.best_bid)}")
        self._ba_lbl.setText(f"UP ask: {_fmt_prob(u.best_ask)}")
        self._mid_dn_lbl.setText(f"DOWN mid: {_fmt_prob(u.down_mid)}")
        self._bb_dn_lbl.setText(f"DOWN bid: {_fmt_prob(u.down_best_bid)}")
        self._ba_dn_lbl.setText(f"DOWN ask: {_fmt_prob(u.down_best_ask)}")

        def fill(table: QTableWidget, rows: list) -> None:
            table.setSortingEnabled(False)
            table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                d = row.to_camel_dict() if hasattr(row, "to_camel_dict") else row
                price = str(d.get("price", ""))
                size = str(d.get("size", ""))
                table.setItem(r, 0, QTableWidgetItem(price))
                table.setItem(r, 1, QTableWidgetItem(_fmt_cents(price)))
                table.setItem(r, 2, QTableWidgetItem(size))

        fill(self._asks, list(u.asks))
        fill(self._bids, list(u.bids))
        fill(self._asks_dn, list(u.down_asks))
        fill(self._bids_dn, list(u.down_bids))

        if u.best_ask is not None and u.best_ask > 0 and u.best_ask == u.best_ask:
            uq = quantize_arb_price(float(u.best_ask))
            if uq is not None:
                self._up_ask_hist.append((int(u.updated_at_ms), uq))
        if u.down_best_ask is not None and u.down_best_ask > 0 and u.down_best_ask == u.down_best_ask:
            dq = quantize_arb_price(float(u.down_best_ask))
            if dq is not None:
                self._dn_ask_hist.append((int(u.updated_at_ms), dq))

        if (
            u.best_ask is not None
            and u.down_best_ask is not None
            and u.best_ask > 0
            and u.down_best_ask > 0
            and u.best_ask == u.best_ask
            and u.down_best_ask == u.down_best_ask
        ):
            uq = quantize_arb_price(float(u.best_ask))
            dq = quantize_arb_price(float(u.down_best_ask))
            if uq is not None and dq is not None:
                self._pair_gross_hist.append((int(u.updated_at_ms), uq + dq))

        self._last_u = u
        self._update_arb_ui(u)
        self._status_slug_lbl.setText((u.slug or "—")[:96])
        self.statusBar().showMessage("Live · WebSocket order book", 0)
        self._consider_rising_leg_stagger_trade()
        self._consider_keep_balance()

    def _on_keep_balance_toggled(self, checked: bool) -> None:
        try:
            sqlite_save_secret("pm_keep_balance", "1" if checked else "0")
        except Exception:
            pass
        self._toast_msg(
            f"Auto balance (UP vs DOWN from session log): {'ON' if checked else 'OFF'} "
            f"(saved to SQLite when possible).",
            kind="info",
            duration_ms=4000,
        )
        self._consider_keep_balance()

    def _consider_keep_balance(self) -> None:
        if self._closing or not self._cb_keep_balance.isChecked():
            return
        if self._balance_scheduled or self._clob_trade_inflight:
            return
        if self._seq_stagger_scheduled or self._seq_stagger_inflight:
            return
        now = time.monotonic()
        cd = float(self._sb_balance_cd.value())
        if self._balance_last_fire >= 0.0 and now - self._balance_last_fire < cd:
            return

        u = self._last_u
        if u is None or not (u.slug or "").strip():
            return
        slug = (u.slug or "").strip()
        thr = float(self._dsp_balance_threshold.value())
        up_s, dn_s = session_leg_shares_for_slug(self._trade_history, slug=slug)
        diff = up_s - dn_s
        if abs(diff) < thr:
            return

        leg = "DOWN" if diff > 0 else "UP"
        leg_u = leg
        if leg_u == "UP":
            if not u.asset_id:
                return
            row_sz = self._row_size(u.asks, 0)
        else:
            if not u.down_asset_id:
                return
            row_sz = self._row_size(u.down_asks, 0)
        if row_sz is None or float(row_sz) <= 0:
            return
        imb = abs(diff)
        clip = min(KEEP_BALANCE_CLIP_MAX_SH, float(row_sz), imb)
        if clip <= 1e-9:
            return

        simulate = self._cb_sim.isChecked()
        if not simulate:
            if not clob_client_available():
                return
            pk = (private_key_from_env() or sqlite_load_secret("pm_private_key") or "").strip()
            if not pk:
                return

        self._balance_scheduled = True
        asyncio.ensure_future(self._keep_balance_buy_wrapped(leg, clip))

    async def _keep_balance_buy_wrapped(self, leg: str, clip_shares: float) -> None:
        try:
            await self._execute_single_leg_impl(leg, show_result_dialog=False, clip_shares=clip_shares)
        except Exception as e:
            _log.warning("Keep balance BUY: %s", e)
        finally:
            self._balance_last_fire = time.monotonic()
            self._balance_scheduled = False

    def _consider_rising_leg_stagger_trade(self) -> None:
        if self._closing or not self._cb_rise_stagger.isChecked():
            return
        if self._seq_stagger_scheduled or self._seq_stagger_inflight:
            return
        if self._clob_trade_inflight or self._balance_scheduled:
            return
        now = time.monotonic()
        if now < self._seq_stagger_cd_until:
            return

        u = self._last_u
        if u is None or not u.down_asset_id:
            return

        win_ms = max(1, int(self._sb_cross_win.value()) * 1000)
        now_ms = int(u.updated_at_ms)
        min_b = float(self._sb_rise_stagger_min.value())

        up_r = rise_bps_vs_window_min(list(self._up_ask_hist), now_ms=now_ms, window_ms=win_ms)
        dn_r = rise_bps_vs_window_min(list(self._dn_ask_hist), now_ms=now_ms, window_ms=win_ms)
        plan = staggered_hedge_order(up_r, dn_r, min_rise_bps=min_b)

        if plan is None:
            if (up_r is None or up_r < min_b) and (dn_r is None or dn_r < min_b):
                self._seq_stagger_armed = True
            return

        first, _second = plan
        leader_rise = up_r if first == "UP" else dn_r
        if leader_rise is None:
            return
        if leader_rise < min_b:
            self._seq_stagger_armed = True
            return
        if not self._seq_stagger_armed:
            return

        simulate = self._cb_sim.isChecked()
        if not simulate:
            if not clob_client_available():
                return
            pk = (private_key_from_env() or sqlite_load_secret("pm_private_key") or "").strip()
            if not pk:
                return

        self._seq_stagger_scheduled = True
        asyncio.ensure_future(self._rising_stagger_wrapped(plan[0], plan[1]))

    async def _rising_stagger_wrapped(self, first: str, second: str) -> None:
        self._seq_stagger_inflight = True
        u0 = self._last_u
        slug0 = u0.slug if u0 else ""
        try:
            await self._execute_single_leg_impl(first, show_result_dialog=False)
            dly = max(0.0, float(self._dsp_rise_stagger_delay.value()))
            if dly > 0.0:
                await asyncio.sleep(dly)
            u1 = self._last_u
            if u1 is None or u1.slug != slug0:
                _log.info("Rising stagger: skipped 2nd leg (market changed).")
                return
            await self._execute_single_leg_impl(second, show_result_dialog=False)
        except Exception as e:
            _log.warning("Rising stagger pair: %s", e)
        finally:
            pair_cd = max(
                float(PAIR_STAGGER_COOLDOWN_MIN_S),
                float(self._sb_rise_stagger_cd.value()),
            )
            self._seq_stagger_cd_until = time.monotonic() + pair_cd
            self._seq_stagger_scheduled = False
            self._seq_stagger_inflight = False
            self._seq_stagger_armed = False

    def _row_size(self, rows: list, idx: int = 0) -> Optional[float]:
        if not rows or idx >= len(rows):
            return None
        try:
            return float(rows[idx].size)
        except (TypeError, ValueError):
            return None

    def _refresh_arb_label(self) -> None:
        if self._last_u is not None:
            self._update_arb_ui(self._last_u)
            self._consider_keep_balance()

    def _update_arb_ui(self, u: BtcOrderbookUpdate) -> None:
        fee = self._fee_bps.value() / 10000.0
        up_sz = self._row_size(u.asks, 0)
        dn_sz = self._row_size(u.down_asks, 0)
        sim = self._cb_sim.isChecked()
        pk_live = (private_key_from_env() or sqlite_load_secret("pm_private_key") or "").strip()
        allow_live = clob_client_available() and bool(pk_live)
        can_fire = sim or allow_live

        def refresh_leg_buttons() -> None:
            self._btn_buy_up.setEnabled(
                can_fire
                and bool(u.asset_id)
                and u.best_ask is not None
                and float(u.best_ask) > 0
                and up_sz is not None
                and up_sz > 0
            )
            self._btn_buy_dn.setEnabled(
                can_fire
                and bool(u.down_asset_id)
                and u.down_best_ask is not None
                and float(u.down_best_ask) > 0
                and dn_sz is not None
                and dn_sz > 0
            )

        if not u.down_asset_id:
            refresh_leg_buttons()
            self._arb_lbl.setText(
                "No DOWN token — DOWN execute disabled; cross-time pair floor needs both outcomes. "
                "You can still BUY UP when the UP book shows size."
            )
            self._swing_hint_lbl.setText("")
            return

        cross_block = ""
        win_ms = max(1, int(self._sb_cross_win.value()) * 1000)
        ct = cross_time_min_ask_sum_vs_par(
            up_samples=self._up_ask_hist,
            down_samples=self._dn_ask_hist,
            now_ms=int(u.updated_at_ms),
            window_ms=win_ms,
            fee_rate_each_leg=fee,
        )
        if ct is not None:
            a_u, t_u, a_d, t_d, g_ct, n_ct, v_ct = ct
            wsec = int(self._sb_cross_win.value())
            flag = " **Sub-$1 combined floor in window (t1 and t2 can differ).**" if v_ct < 0 else ""
            cross_block = (
                f"Cross-time ({wsec}s): min UP {a_u:.4f} @ {_fmt_ts_ms(t_u)} (t1), "
                f"min DOWN {a_d:.4f} @ {_fmt_ts_ms(t_d)} (t2) → gross {g_ct:.4f}, net {n_ct:.4f} "
                f"({v_ct:+.4f} vs $1 par). Diagnostic only; each Execute button sends **one** "
                f"`post_order` at the **current** ask for that leg.{flag}"
            )

        paper = buy_bundle_opportunity_at_asks(
            up_best_ask=u.best_ask,
            down_best_ask=u.down_best_ask,
            up_ask_size=up_sz,
            down_ask_size=dn_sz,
            fee_rate_each_leg=fee,
        )
        refresh_leg_buttons()

        parts: list[str] = []
        if cross_block:
            parts.append(cross_block)
        head = "\n".join(parts) if parts else ""

        slug_bal = (u.slug or "").strip()
        bal_suffix = ""
        if slug_bal:
            bu, bd = session_leg_shares_for_slug(self._trade_history, slug=slug_bal)
            bal_suffix = (
                f"\nLogged session size (this slug): UP {bu:.4f} sh · DOWN {bd:.4f} sh — "
                "used by **Auto BUY to balance** (counts rows logged with a leg tag)."
            )

        if paper is None:
            tail = (
                "No paired hypothetical two-leg size at current best asks (depth missing on a leg). "
                "Per-leg buttons still enable when that leg alone has ask depth."
            )
            if sim and not pk_live:
                tail += " Sim: no PM_PRIVATE_KEY required."
            self._arb_lbl.setText(((head + "\n" + tail).strip() if head else tail) + bal_suffix)
        else:
            tail = (
                f"Hypothetical same-touch pair: up to {paper.max_size:.2f} matched shares at net "
                f"{paper.bundle_cost_or_proceeds:.4f} vs $1 ({paper.edge_per_unit:+.4f} edge/unit after fees). "
                "Execution is **not** bundled: BUY UP / BUY DOWN each fire a single leg (≤5 sh per click)."
            )
            if sim and not pk_live:
                tail += " Sim: paper without PM_PRIVATE_KEY."
            self._arb_lbl.setText(((head + "\n" + tail).strip() if head else tail) + bal_suffix)

        sw = pair_swing_summary(
            list(self._pair_gross_hist),
            now_ms=int(u.updated_at_ms),
            window_ms=win_ms,
            rise_min_bps=float(self._sb_swing_rise.value()),
            pullback_bps=float(self._sb_swing_pull.value()),
            recovery_bps=float(self._sb_swing_rec.value()),
        )
        self._swing_hint_lbl.setText(sw if sw else "— (collecting pair-gross samples…)")

    def _update_trade_pnl_cumulative(self) -> None:
        sim_p, real_p = cumulative_pnl_by_mode(self._trade_history)
        self._trade_pnl_lbl.setText(
            "Session cumulative (est. @ $1 / pair; single-leg rows PnL $0) — "
            f"Sim: ${sim_p:.4f} | Real: ${real_p:.4f}"
        )

    def _append_single_leg_trade_row(
        self,
        *,
        leg: str,
        simulate: bool,
        slug: str,
        shares: float,
        price: float,
        fee_bps: int,
        resp: Any,
    ) -> None:
        m = single_leg_buy_cost(shares=shares, price=price, fee_bps_each_leg=float(fee_bps))
        leg_u = "UP" if leg.upper() == "UP" else "DOWN"
        up_px = f"{price:.4f}" if leg_u == "UP" else "—"
        dn_px = f"{price:.4f}" if leg_u == "DOWN" else "—"
        up_cell = format_clob_response_cell(resp) if leg_u == "UP" else "—"
        dn_cell = format_clob_response_cell(resp) if leg_u == "DOWN" else "—"
        snap: dict[str, Any] = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "mode": "SIM" if simulate else "REAL",
            "slug": (slug or "")[:80],
            "leg": leg_u,
            "shares": float(shares),
            "cost_est": float(m["total_cost"]),
            "fee_est": float(m["fee_leg"]),
            "pnl_est": 0.0,
        }
        self._trade_history.insert(0, snap)
        if len(self._trade_history) > 200:
            self._trade_history.pop()

        t = self._trade_table
        t.insertRow(0)
        cells = [
            snap["time"],
            snap["mode"],
            snap["slug"],
            f"{snap['shares']:.4f}",
            up_px,
            dn_px,
            f"{snap['cost_est']:.4f}",
            f"{snap['fee_est']:.4f}",
            f"{snap['pnl_est']:.4f}",
            up_cell,
            dn_cell,
        ]
        for col, text in enumerate(cells):
            t.setItem(0, col, QTableWidgetItem(text))
        while t.rowCount() > 60:
            t.removeRow(t.rowCount() - 1)
            if self._trade_history:
                self._trade_history.pop()
        self._update_trade_pnl_cumulative()

    async def _execute_single_leg_impl(
        self,
        leg: str,
        *,
        show_result_dialog: bool,
        clip_shares: Optional[float] = None,
    ) -> None:
        if self._clob_trade_inflight:
            return
        self._clob_trade_inflight = True
        try:
            u = self._last_u
            if u is None:
                return
            leg_u = "UP" if str(leg).upper() == "UP" else "DOWN"
            if leg_u == "UP":
                if not u.asset_id:
                    if show_result_dialog:
                        self._toast_msg("CLOB: Missing UP token id.", kind="warn", duration_ms=6000)
                    return
                row_sz = self._row_size(u.asks, 0)
                price = u.best_ask
                token_id = u.asset_id
            else:
                if not u.down_asset_id:
                    if show_result_dialog:
                        self._toast_msg("CLOB: Missing DOWN token id.", kind="warn", duration_ms=6000)
                    return
                row_sz = self._row_size(u.down_asks, 0)
                price = u.down_best_ask
                token_id = u.down_asset_id

            if price is None or row_sz is None or float(price) <= 0 or float(row_sz) <= 0:
                if show_result_dialog:
                    self._toast_msg(
                        f"CLOB: No {leg_u} size at current best ask.",
                        kind="info",
                        duration_ms=5500,
                    )
                return

            simulate = self._cb_sim.isChecked()
            pk = (private_key_from_env() or sqlite_load_secret("pm_private_key") or "").strip()
            if not simulate and not pk:
                if show_result_dialog:
                    self._toast_msg(
                        "CLOB: Set PM_PRIVATE_KEY in .env (see .env.example) or save pm_private_key in SQLite.",
                        kind="warn",
                        duration_ms=8000,
                    )
                return
            if simulate and pk:
                sig_type = sig_type_resolve(sqlite_load_secret("pm_sig_type"))
                funder_raw = funder_from_env() or sqlite_load_secret("pm_funder")
                funder = funder_resolve_for_clob(pk, sig_type, funder_raw)
            elif simulate:
                sig_type = 0
                funder = ""
            else:
                sig_type = sig_type_resolve(sqlite_load_secret("pm_sig_type"))
                funder_raw = funder_from_env() or sqlite_load_secret("pm_funder")
                funder = funder_resolve_for_clob(pk, sig_type, funder_raw)

            size = min(float(row_sz), 5.0)
            if clip_shares is not None:
                size = min(size, max(0.0, float(clip_shares)))
            if size <= 0:
                if show_result_dialog:
                    self._toast_msg("CLOB: Size is zero.", kind="warn", duration_ms=5000)
                return

            pk_arg = pk if pk else ""
            try:
                r = await buy_single_leg_fak(
                    host="https://clob.polymarket.com",
                    chain_id=137,
                    private_key=pk_arg,
                    funder=str(funder).strip(),
                    signature_type=sig_type,
                    leg=leg_u,
                    token_id=str(token_id),
                    price=float(price),
                    size=size,
                    simulate=simulate,
                )
                self._append_single_leg_trade_row(
                    leg=leg_u,
                    simulate=simulate,
                    slug=u.slug,
                    shares=size,
                    price=float(price),
                    fee_bps=self._fee_bps.value(),
                    resp=r,
                )
                m = single_leg_buy_cost(
                    shares=size,
                    price=float(price),
                    fee_bps_each_leg=float(self._fee_bps.value()),
                )
                if show_result_dialog:
                    title = "CLOB (simulated)" if simulate else "CLOB response"
                    self._toast_msg(
                        f"{title}\n\nLogged to Trading log ({leg_u} leg only).\n"
                        f"Est. leg cost: ${m['total_cost']:.4f}\n"
                        f"Est. leg fee: ${m['fee_leg']:.4f}\n"
                        f"Pair-resolution PnL is not estimated for a single leg (see log PnL $0).\n\n"
                        f"{leg_u}: {format_clob_response_cell(r, max_len=120)}",
                        kind="info",
                        duration_ms=10000,
                    )
                else:
                    self._toast_msg(
                        f"CLOB {leg_u} {u.slug} sim={simulate} cost~${m['total_cost']:.4f}",
                        kind="info",
                        duration_ms=4500,
                    )
                    _log.info(
                        "CLOB %s %s size=%.4f cost~%.4f sim=%s",
                        leg_u,
                        u.slug,
                        size,
                        float(m["total_cost"]),
                        simulate,
                    )
            except Exception as e:
                self._toast_msg(f"CLOB error: {e}", kind="error", duration_ms=9000)
                if not show_result_dialog:
                    _log.warning("CLOB single leg error: %s", e)
        finally:
            self._clob_trade_inflight = False

    async def _on_check_set_approvals(self) -> None:
        if self._approvals_inflight:
            return
        self._approvals_inflight = True
        try:
            await self._on_check_set_approvals_body()
        finally:
            self._approvals_inflight = False

    async def _on_check_set_approvals_body(self) -> None:
        try:
            from polymarket_analyzer.chain.approvals import (
                approvals_dependencies_available,
                ensure_trading_approvals,
            )
        except ImportError as e:
            self._toast_msg(
                f"Approvals: missing dependency: {e}\nInstall: pip install web3 py-clob-client-v2",
                kind="warn",
                duration_ms=9000,
            )
            return
        if not approvals_dependencies_available():
            self._toast_msg(
                "Approvals: install web3 and py-clob-client-v2, then restart the app.",
                kind="warn",
                duration_ms=8000,
            )
            return
        pk = private_key_from_env() or sqlite_load_secret("pm_private_key")
        if not pk:
            self._toast_msg(
                "Approvals: set PM_PRIVATE_KEY in .env or save pm_private_key in SQLite.",
                kind="warn",
                duration_ms=8000,
            )
            return
        sig_type = sig_type_resolve(sqlite_load_secret("pm_sig_type"))
        funder_raw = funder_from_env() or sqlite_load_secret("pm_funder")
        funder_resolved = funder_resolve_for_clob(str(pk).strip(), sig_type, funder_raw)

        bk = builder_key_from_env() or sqlite_load_secret("pm_builder_key")
        bs = builder_secret_from_env() or sqlite_load_secret("pm_builder_secret")
        bp = builder_passphrase_from_env() or sqlite_load_secret("pm_builder_passphrase")
        rpc = rpc_url_from_env()

        def _run() -> dict:
            return ensure_trading_approvals(
                private_key=str(pk).strip(),
                funder=funder_resolved,
                signature_type=sig_type,
                rpc_url=rpc,
                builder_key=bk,
                builder_secret=bs,
                builder_passphrase=bp,
            )

        try:
            out = await asyncio.to_thread(_run)
        except Exception as e:
            self._toast_msg(f"Approvals failed: {e}", kind="error", duration_ms=10000)
            return

        al = out.get("allowances") or {}
        lines = [
            f"EOA (signer): {out.get('eoa')}",
            f"Trading vault (allowance owner): {out.get('trading_address')}",
            f"PM_SIG_TYPE: {out.get('signature_type')}",
            "",
            "pUSD / CTF flags (standard exchange, neg-risk exchange, CTF std, CTF neg-risk):",
            f"  {al.get('usdc_exchange')} / {al.get('usdc_neg_risk')} / {al.get('ctf_exchange')} / {al.get('ctf_neg_risk')}",
            "",
        ]
        txh = out.get("tx_hashes") or []
        if txh:
            lines.append("Submitted EOA transactions:")
            lines.extend(f"  {h}" for h in txh)
        if out.get("relayer_transaction_id"):
            lines.append(f"Relayer transaction id: {out.get('relayer_transaction_id')}")
        if out.get("relayer_transaction_hash"):
            lines.append(f"Relayer transaction hash: {out.get('relayer_transaction_hash')}")
        if not txh and not out.get("relayer_transaction_id"):
            lines.append("No new approval transactions were submitted (allowances were already sufficient).")
        lines.append(f"Allowances sufficient for trading now: {out.get('already_sufficient')}")
        self._toast_msg("Trading approvals\n\n" + "\n".join(lines), kind="info", duration_ms=14000)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing:
            event.accept()
            return
        event.ignore()
        self._closing = True
        self._wallet_timer.stop()
        self._toast.hide_immediately()
        sb = self.statusBar()
        if sb is not None:
            sb.showMessage("Shutting down…", 0)
        asyncio.ensure_future(self._shutdown())

    async def _shutdown(self) -> None:
        try:
            if self._supervisor is not None:
                self._supervisor.stop()
                try:
                    await asyncio.wait_for(self._supervisor.join(), timeout=8.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
            if self._http is not None:
                await self._http.aclose()
        finally:
            app = QApplication.instance()
            if app is not None:
                app.quit()
