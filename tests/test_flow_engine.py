from mats.flow.engine import FlowState


def _book(mid: float, n: int = 20, qty: float = 100.0, wall_at: float | None = None):
    # $10k per level so the wall (20x) clears the $2k / 3%-of-depth floor
    bids = [(mid * (1 - 0.0005 * (i + 1)), qty) for i in range(n)]
    asks = [(mid * (1 + 0.0005 * (i + 1)), qty) for i in range(n)]
    if wall_at:
        asks = [(p, qty * 20 if abs(p - wall_at) < 1e-9 else q) for p, q in asks]
    return bids, asks


def test_windows_split_aggressor_side() -> None:
    s = FlowState("XUSDT")
    s.on_trade(100.0, 10.0, 5.0, True)  # $50 buy
    s.on_trade(105.0, 10.0, 2.0, False)  # $20 sell
    s.on_trade(200.0, 10.0, 1.0, True)  # $10 buy, later
    w = s.window(200.0, 10)
    assert (w.buy, w.sell) == (10.0, 0.0)
    w = s.window(200.0, 300)
    assert (w.buy, w.sell) == (60.0, 20.0)
    assert s.cvd == 40.0


def test_band_and_imbalance() -> None:
    s = FlowState("XUSDT")
    bids, asks = _book(100.0)
    s.on_book(0, bids, asks)
    b, a = s.band(0.25)
    assert b > 0 and a > 0 and abs(b - a) / b < 0.01


def test_wall_pulled_vs_eaten() -> None:
    s = FlowState("XUSDT")
    s.last_price = 100.0
    bids, asks = _book(100.0)
    wall = asks[3][0]
    s.on_book(0, *_book(100.0, wall_at=wall))
    assert any(w.side == "ask" for w in s.walls.values())
    s.on_book(15, bids, asks)  # wall gone after 15s, price never reached it
    assert s.wall_events[-1].kind == "pulled"

    s.on_book(20, *_book(100.0, wall_at=wall))
    s.last_price = wall + 0.01  # price traded through
    s.on_book(40, bids, asks)
    assert s.wall_events[-1].kind == "eaten"


def test_absorption_detects_selling_that_does_not_move_price() -> None:
    s = FlowState("XUSDT")
    t = 1000.0
    for i in range(200):  # quiet baseline over 5m
        s.on_trade(t + i, 100.0, 0.1, i % 2 == 0)
    now = t + 300
    for i in range(30):  # heavy selling, price flat
        s.on_trade(now - 30 + i, 100.0, 5.0, False)
    s.detect_absorption(now)
    assert s.absorption and s.absorption[-1][1].level == "bull"


def test_oi_regime() -> None:
    s = FlowState("XUSDT")
    s.on_trade(0, 100.0, 1, True)
    s.on_open_interest(0, 1000)
    s.on_trade(60, 101.0, 1, True)
    s.on_open_interest(60, 1010)
    assert s.oi_regime(60, 60) == "new longs opening"
