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


class InstrumentStats(BaseModel):
    symbol: str
    ts: datetime
    last_price: float
    mark_price: float
    funding_rate_pct: float
    open_interest: float
    quote_volume_24h: float


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
