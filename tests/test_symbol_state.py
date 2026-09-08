from __future__ import annotations

from datetime import UTC, datetime

from mats.config import StrategyParams
from mats.core.models import Candle, Trade

BASE = 1_700_000_000


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC)


def _state():
    from mats.agents.symbol_state import SymbolState

    return SymbolState("X", StrategyParams())


def test_returns_from_candles() -> None:
    s = _state()
    for i in range(70):
        price = 100.0 + i  # steady climb
        s.on_candle(
            Candle(
                symbol="X",
                interval="1m",
                open_time=_dt(BASE + i * 60),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=1.0,
            )
        )
    # 5 minutes ago close was 164, now 169 -> ~+3.05%
    assert s.ret_5m is not None and abs(s.ret_5m - (169 / 164 - 1) * 100) < 1e-6
    assert s.ret_1h is not None and s.ret_1h > 0


def test_non_1m_candles_ignored() -> None:
    s = _state()
    s.on_candle(
        Candle(
            symbol="X", interval="5m", open_time=_dt(BASE), open=1, high=1, low=1, close=1, volume=1
        )
    )
    assert s.ret_5m is None


def test_cvd_divergence_detects_price_high_without_cvd_high() -> None:
    s = _state()
    # first half: price rises to 110 on strong buying (cvd up)
    for i in range(15):
        s.on_trade(
            Trade(symbol="X", ts=_dt(BASE + i), price=100.0 + i, qty=1.0, is_buyer_maker=False)
        )
    # second half: price pushes to a new high 120 but only on sellers pulling (net selling)
    for i in range(15, 30):
        s.on_trade(
            Trade(symbol="X", ts=_dt(BASE + i), price=105.0 + i, qty=1.0, is_buyer_maker=True)
        )
    assert s.cvd_divergence is True


def test_cvd_no_divergence_when_cvd_confirms() -> None:
    s = _state()
    for i in range(30):
        s.on_trade(
            Trade(symbol="X", ts=_dt(BASE + i), price=100.0 + i, qty=1.0, is_buyer_maker=False)
        )
    assert s.cvd_divergence is False


def test_tps_ratio_none_until_enough_trades() -> None:
    s = _state()
    for i in range(5):
        s.on_trade(Trade(symbol="X", ts=_dt(BASE + i), price=1.0, qty=1.0, is_buyer_maker=False))
    assert s.tps_ratio is None
