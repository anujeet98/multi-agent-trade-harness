from __future__ import annotations

from mats.feeds.symbols import (
    SymbolMap,
    canonical_to_coindcx,
    coindcx_to_canonical,
)


def test_roundtrip() -> None:
    assert coindcx_to_canonical("B-BTC_USDT") == "BTCUSDT"
    assert canonical_to_coindcx("BTCUSDT") == "B-BTC_USDT"
    assert coindcx_to_canonical("not-a-pair") is None
    assert canonical_to_coindcx("BTCINR") is None


def test_universe_and_data_source() -> None:
    sm = SymbolMap(
        binance_symbols={"BTCUSDT", "ETHUSDT"},
        coindcx_pairs={"B-BTC_USDT", "B-ETH_USDT", "B-ARX_USDT"},
    )
    assert sm.tradeable_universe() == {"BTCUSDT", "ETHUSDT", "ARXUSDT"}
    assert sm.has_binance_data("BTCUSDT") is True
    assert sm.has_binance_data("ARXUSDT") is False  # CoinDCX-only alt
    assert sm.coindcx_pair("ARXUSDT") == "B-ARX_USDT"


def test_override() -> None:
    sm = SymbolMap(coindcx_pairs=set(), overrides={"1000PEPEUSDT": "B-PEPE_USDT"})
    assert sm.coindcx_pair("1000PEPEUSDT") == "B-PEPE_USDT"
    assert "1000PEPEUSDT" in sm.tradeable_universe()
