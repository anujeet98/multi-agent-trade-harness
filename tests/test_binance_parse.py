from __future__ import annotations

from mats.core.models import Candle, Liquidation, MarkPrice, OrderBook, Side, Trade
from mats.feeds.binance import parse_ws


def _env(stream: str, data: dict) -> dict:
    return {"stream": stream, "data": data}


def test_parse_agg_trade() -> None:
    ev = parse_ws(
        _env(
            "btcusdt@aggTrade",
            {
                "e": "aggTrade",
                "s": "BTCUSDT",
                "p": "60000.5",
                "q": "0.10",
                "T": 1_700_000_000_000,
                "m": True,
            },
        )
    )
    assert isinstance(ev, Trade)
    assert ev.price == 60000.5 and ev.qty == 0.1
    assert ev.is_buyer_maker is True  # aggressor was a seller


def test_parse_kline_only_closed() -> None:
    base = {"e": "kline", "s": "ETHUSDT"}
    k = {
        "s": "ETHUSDT",
        "i": "1m",
        "t": 1_700_000_000_000,
        "o": "1",
        "h": "2",
        "l": "0.5",
        "c": "1.5",
        "v": "100",
    }
    assert parse_ws(_env("ethusdt@kline_1m", {**base, "k": {**k, "x": False}})) is None
    ev = parse_ws(_env("ethusdt@kline_1m", {**base, "k": {**k, "x": True}}))
    assert isinstance(ev, Candle) and ev.high == 2.0 and ev.interval == "1m"


def test_parse_depth() -> None:
    ev = parse_ws(
        _env(
            "btcusdt@depth20@100ms",
            {
                "e": "depthUpdate",
                "s": "BTCUSDT",
                "T": 1_700_000_000_000,
                "b": [["100", "3"], ["99", "1"]],
                "a": [["101", "2"]],
            },
        )
    )
    assert isinstance(ev, OrderBook)
    assert ev.bids[0].price == 100.0 and ev.asks[0].qty == 2.0


def test_parse_mark_price() -> None:
    ev = parse_ws(
        _env(
            "btcusdt@markPrice@1s",
            {
                "e": "markPriceUpdate",
                "s": "BTCUSDT",
                "E": 1_700_000_000_000,
                "p": "60010",
                "r": "0.0001",
                "T": 1_700_000_600_000,
            },
        )
    )
    assert isinstance(ev, MarkPrice)
    assert ev.mark_price == 60010.0
    assert abs(ev.funding_rate_pct - 0.01) < 1e-9


def test_parse_force_order_side() -> None:
    ev = parse_ws(
        _env(
            "!forceOrder@arr",
            {
                "e": "forceOrder",
                "o": {
                    "s": "BTCUSDT",
                    "S": "SELL",
                    "q": "0.5",
                    "p": "59000",
                    "ap": "58990",
                    "T": 1_700_000_000_000,
                },
            },
        )
    )
    assert isinstance(ev, Liquidation)
    assert ev.side is Side.LONG  # a long was force-sold
    assert ev.price == 58990.0


def test_unknown_stream_ignored() -> None:
    assert parse_ws(_env("btcusdt@somethingelse", {"e": "x"})) is None
