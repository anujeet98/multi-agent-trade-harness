from __future__ import annotations

from mats.feeds.coindcx import parse_candles, parse_instrument, parse_orderbook


def test_parse_candles() -> None:
    payload = {
        "data": [
            {
                "time": 1_700_000_000_000,
                "open": "0.15",
                "high": "0.16",
                "low": "0.149",
                "close": "0.158",
                "volume": "12000",
            },
        ]
    }
    out = parse_candles("B-ARX_USDT", "1m", payload)
    assert len(out) == 1
    c = out[0]
    assert c.symbol == "ARXUSDT" and c.close == 0.158 and c.interval == "1m"


def test_parse_orderbook_dict_shape() -> None:
    payload = {
        "bids": {"99.0": "5", "98.5": "10", "99.5": "2"},
        "asks": {"100.5": "4", "100.0": "1"},
    }
    ob = parse_orderbook("B-BTC_USDT", payload)
    assert [lvl.price for lvl in ob.bids] == [99.5, 99.0, 98.5]
    assert [lvl.price for lvl in ob.asks] == [100.0, 100.5]


def test_parse_orderbook_list_shape() -> None:
    payload = {
        "bids": [["99.0", "5"], ["99.5", "2"]],
        "asks": [["100.5", "4"], ["100.0", "1"]],
    }
    ob = parse_orderbook("B-BTC_USDT", payload)
    assert [lvl.price for lvl in ob.bids] == [99.5, 99.0]
    assert [lvl.price for lvl in ob.asks] == [100.0, 100.5]


def test_parse_orderbook_missing_side() -> None:
    ob = parse_orderbook("B-BTC_USDT", {"bids": {"99.0": "5"}})
    assert ob.asks == [] and ob.bids[0].price == 99.0


def test_parse_instrument() -> None:
    payload = {
        "instrument": {
            "pair": "B-BTC_USDT",
            "price_increment": "0.1",
            "quantity_increment": "0.001",
            "min_quantity": "0.001",
            "max_leverage": "20",
            "maker_fee": "0.02",
            "taker_fee": "0.05",
        }
    }
    spec = parse_instrument(payload)
    assert spec.symbol == "BTCUSDT"
    assert spec.tick_size == 0.1 and spec.max_leverage == 20.0 and spec.taker_fee_pct == 0.05
