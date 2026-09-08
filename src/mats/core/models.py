"""Core domain models shared across feeds, agents and the broker."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class Candle(BaseModel):
    symbol: str
    interval: str  # "1m", "5m", ...
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float  # base asset


class Trade(BaseModel):
    symbol: str
    ts: datetime
    price: float
    qty: float
    is_buyer_maker: bool  # False => aggressive buy


class BookLevel(BaseModel):
    price: float
    qty: float


class OrderBook(BaseModel):
    symbol: str
    ts: datetime
    bids: list[BookLevel]
    asks: list[BookLevel]


class Liquidation(BaseModel):
    symbol: str
    ts: datetime
    side: Side  # side that was liquidated
    qty: float
    price: float


class MarkPrice(BaseModel):
    """Live mark price + funding, from a streaming source (e.g. Binance markPrice@1s)."""

    symbol: str
    ts: datetime
    mark_price: float
    funding_rate_pct: float  # per funding interval (8h), as a percentage
    next_funding_time: datetime | None = None


class InstrumentStats(BaseModel):
    """Periodic REST snapshot used by the scanner (Layer 0/1)."""

    symbol: str
    ts: datetime
    last_price: float
    mark_price: float
    funding_rate_pct: float
    open_interest: float
    quote_volume_24h: float  # USDT
    listed_at: datetime | None = None  # contract onboard date, for the E6 age check


class FeedHealth(BaseModel):
    """Emitted by a feed runner when a stream goes stale or recovers.

    The coordinator halts new entries while any subscribed feed is stale.
    """

    source: str  # "binance", "coindcx", ...
    stream: str  # "aggTrade", "depth", "kline_1m", ...
    healthy: bool
    last_message_age_s: float
    ts: datetime


class ContractSpec(BaseModel):
    """Tradeable-contract metadata from CoinDCX (the execution venue)."""

    symbol: str  # canonical, e.g. BTCUSDT
    coindcx_pair: str  # e.g. B-BTC_USDT
    tick_size: float
    step_size: float  # min quantity increment
    min_quantity: float
    max_leverage: float
    maker_fee_pct: float
    taker_fee_pct: float


class Candidate(BaseModel):
    """Scanner output: a coin worth an Observer's attention."""

    symbol: str
    side: Side
    hotness: float
    reasons: dict[str, float]
    created_at: datetime


class TradeIntent(BaseModel):
    """Observer output: a validated entry the Coordinator may act on."""

    symbol: str
    side: Side
    entry_price: float
    stop_price: float
    tp1_price: float
    room_to_run_score: int
    notes: dict[str, str]
    created_at: datetime
