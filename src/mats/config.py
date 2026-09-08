"""Runtime configuration, loaded from environment / .env.

All strategy thresholds live in `StrategyParams` so they can be tuned in one place and,
later, swept by the backtester. See docs/05-ruleset-v1.1.md for the meaning of each.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class StrategyParams(BaseModel):
    """Rule Set v1.1 thresholds. Defaults are backtest-tunable hypotheses, not gospel."""

    # Layer 0 - eligibility
    # Quote volume is USDT-denominated on both Binance and CoinDCX B-*_USDT perps.
    # ~$2M ≈ ₹17cr — the "₹15cr" figure in the docs was an INR-framing slip.
    min_24h_quote_volume_usdt: float = 2_000_000
    max_spread_pct: float = 0.15
    max_abs_funding_pct: float = 0.08
    max_mark_last_gap_pct: float = 0.3
    min_contract_age_days: int = 7

    # Layer 1 - hotness / candidate filter
    min_rvol_5m: float = 3.0
    min_rvol_15m: float = 2.5
    min_tps_ratio: float = 2.0
    ret_1h_band_pct: tuple[float, float] = (3.0, 22.0)
    max_rsi_5m: float = 82.0
    top_gainer_rank_max: int = 20
    scan_interval_s: float = 45.0
    rvol_baseline_window_s: float = 14_400.0  # 4h
    oi_delta_window_s: float = 900.0  # 15m
    cvd_window_s: float = 300.0  # 5m
    rs_vs_btc_window_s: float = 900.0  # 15m
    btc_symbol: str = "BTCUSDT"
    candidates_per_side: int = 5
    # hotness score weights (applied to z-scored features)
    hotness_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "rvol_5m": 1.0,
            "rvol_15m": 1.0,
            "abs_ret_15m": 1.0,
            "tps_ratio": 1.0,
            "oi_delta": 1.0,
            "rs_vs_btc": 1.0,
        }
    )

    # Layer 2 - entry
    room_to_run_min_score: int = 6  # of 9
    retrace_pct_range: tuple[float, float] = (20.0, 50.0)
    resume_candle_min_rvol: float = 1.5
    breakout_min_rvol: float = 3.0
    consolidation_max_width_pct: float = 0.6
    consolidation_min_minutes: int = 3
    min_book_imbalance: float = 0.20
    wall_size_mult: float = 3.0
    max_size_pct_of_60s_vol: float = 8.0
    max_market_cross_size_pct_of_60s_vol: float = 5.0
    max_book_walk_slippage_pct: float = 0.15
    post_fill_scratch_seconds: int = 15
    zigzag_min_move_pct: float = 0.3
    leg_extension_max_mult: float = 1.8  # current leg vs avg leg -> exhausted
    max_atr_above_vwap_mult: float = 3.0  # stretched from anchored VWAP
    resistance_proximity_pct: float = 0.4  # R2: entry too close to a prior swing extreme
    climax_bar_atr_mult: float = 3.0  # R1
    rsi_1m_room_cap: float = 80.0  # room-to-run check 6
    btc_5m_move_reject_pct: float = 1.5  # R5
    min_rs_vs_btc_pct: float = 0.15  # R7: move is pure BTC beta
    observer_watch_seconds: int = 600  # give up hunting an entry after this

    # Layer 3 - execution / management
    risk_per_trade_inr: float = 150.0
    max_effective_leverage: float = 12.0
    max_stop_distance_pct: float = 0.8
    tp1_r_multiple: float = 1.3
    tp1_close_fraction: float = 0.60
    time_stop_seconds: int = 240
    stall_band_pct: float = 0.2

    # Layer 4 - coordinator
    max_concurrent_positions: int = 1
    max_trades_per_hour: int = 6
    consecutive_loss_pause_count: int = 3
    consecutive_loss_pause_hours: int = 2
    daily_loss_stop_pct: float = 20.0
    daily_profit_stop_pct: float = 30.0
    correlated_pair_threshold: float = 0.7


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MATS_", env_file=".env", extra="ignore")

    mode: Mode = Mode.PAPER
    allow_live: bool = False
    log_level: str = "INFO"
    paper_start_capital_inr: float = 1300.0

    coindcx_api_key: str = Field(default="", validation_alias="COINDCX_API_KEY")
    coindcx_api_secret: str = Field(default="", validation_alias="COINDCX_API_SECRET")

    strategy: StrategyParams = StrategyParams()

    def guard_live(self) -> None:
        """Fail loudly unless live trading is doubly opted-in."""
        if self.mode is Mode.LIVE and not self.allow_live:
            raise RuntimeError(
                "MATS_MODE=live requires MATS_ALLOW_LIVE=1. Refusing to place real orders."
            )
