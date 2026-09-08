"""Symbol mapping between the internal canonical symbol and each venue.

Canonical symbol = Binance USDⓈ-M style, e.g. ``BTCUSDT``. Indicators are computed
against this. CoinDCX is where orders are placed, so we also carry its futures pair
string, e.g. ``B-BTC_USDT``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_COINDCX_RE = re.compile(r"^B-([A-Z0-9]+)_([A-Z0-9]+)$")


def coindcx_to_canonical(pair: str) -> str | None:
    """``B-BTC_USDT`` -> ``BTCUSDT``. Returns None if it doesn't look like a futures pair."""
    m = _COINDCX_RE.match(pair)
    if not m:
        return None
    return f"{m.group(1)}{m.group(2)}"


def canonical_to_coindcx(symbol: str, quote: str = "USDT") -> str | None:
    if not symbol.endswith(quote):
        return None
    base = symbol[: -len(quote)]
    return f"B-{base}_{quote}"


@dataclass
class SymbolMap:
    """Which symbols exist where, and how to translate.

    Build from the two venues' instrument lists at startup; `overrides` handles the
    handful of cases where the naming doesn't follow the pattern.
    """

    binance_symbols: set[str] = field(default_factory=set)
    coindcx_pairs: set[str] = field(default_factory=set)
    overrides: dict[str, str] = field(default_factory=dict)  # canonical -> coindcx pair

    def coindcx_pair(self, symbol: str) -> str | None:
        if symbol in self.overrides:
            return self.overrides[symbol]
        return canonical_to_coindcx(symbol)

    def canonical_symbols_on_coindcx(self) -> set[str]:
        out = {v for v in (coindcx_to_canonical(p) for p in self.coindcx_pairs) if v}
        out.update(self.overrides.keys())
        return out

    def tradeable_universe(self) -> set[str]:
        """Coins we can actually trade: listed on CoinDCX. Indicator source is decided
        per-symbol by `has_binance_data`.
        """
        return self.canonical_symbols_on_coindcx()

    def has_binance_data(self, symbol: str) -> bool:
        return symbol in self.binance_symbols
