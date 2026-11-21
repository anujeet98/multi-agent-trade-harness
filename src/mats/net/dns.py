"""Resolve DNS-blocked exchange hosts over DNS-over-HTTPS.

Some Indian ISPs (seen on Jio) answer DNS for Binance hosts such as ``fapi.binance.com``
with a sinkhole address, so every request times out. The real servers are reachable:
only the DNS answer is poisoned. ``install()`` patches ``socket.getaddrinfo`` so the
listed hosts are resolved through Cloudflare/Google DoH instead. TLS still verifies
against the real hostname (SNI and certificate checks are untouched), and every other
host keeps using the system resolver. httpx, websockets and asyncio all resolve through
``socket.getaddrinfo``, so one call covers REST and WebSocket.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import threading
import time
import urllib.request
from collections.abc import Callable, Iterable

DOH_ENDPOINTS = (
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/resolve",
)
# Hosts we route through DoH. Only Binance is blocked today; add others here if needed.
DEFAULT_HOSTS = frozenset(
    {
        "fapi.binance.com",
        "fstream.binance.com",
        "api.binance.com",
        "stream.binance.com",
        "dapi.binance.com",
        "dstream.binance.com",
    }
)
_TTL_FLOOR_S = 60.0

_lock = threading.Lock()
_hosts: set[str] = set()
_cache: dict[str, tuple[float, list[str]]] = {}  # host -> (expires_at, ipv4 list)
_orig_getaddrinfo: Callable[..., list] | None = None

Fetch = Callable[[str], bytes]


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
    # DoH endpoints are fixed public hosts resolved by the system resolver (not blocked).
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.read()


def parse_doh(body: bytes) -> tuple[list[str], float]:
    """DoH JSON answer -> (IPv4 addresses, ttl seconds). CNAME records are skipped."""
    data = json.loads(body)
    ips, ttls = [], []
    for ans in data.get("Answer") or []:
        if ans.get("type") == 1:  # A record
            try:
                ipaddress.IPv4Address(ans["data"])
            except (KeyError, ValueError):
                continue
            ips.append(ans["data"])
            ttls.append(float(ans.get("TTL", _TTL_FLOOR_S)))
    return ips, max(_TTL_FLOOR_S, min(ttls) if ttls else _TTL_FLOOR_S)


def resolve(host: str, fetch: Fetch = _http_get, now: Callable[[], float] = time.time) -> list[str]:
    """IPv4 addresses for ``host`` via DoH, cached for the record TTL. [] if all DoH fail."""
    with _lock:
        hit = _cache.get(host)
        if hit and hit[0] > now():
            return hit[1]
    for endpoint in DOH_ENDPOINTS:
        try:
            ips, ttl = parse_doh(fetch(f"{endpoint}?name={host}&type=A"))
        except (OSError, ValueError):
            continue
        if ips:
            with _lock:
                _cache[host] = (now() + ttl, ips)
            return ips
    return []


def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    assert _orig_getaddrinfo is not None
    name = host.decode() if isinstance(host, bytes) else host
    if isinstance(name, str) and name.lower() in _hosts and family in (0, socket.AF_INET):
        ips = resolve(name.lower())
        if ips:
            out = []
            for ip in ips:
                out += _orig_getaddrinfo(ip, port, socket.AF_INET, type, proto, flags)
            return out
        # DoH unreachable: fall back to the system answer rather than failing outright.
    return _orig_getaddrinfo(host, port, family, type, proto, flags)


def install(hosts: Iterable[str] = DEFAULT_HOSTS) -> None:
    """Route ``hosts`` through DoH for this process. Idempotent; safe to call repeatedly."""
    global _orig_getaddrinfo
    with _lock:
        _hosts.update(h.lower() for h in hosts)
        if _orig_getaddrinfo is None:
            _orig_getaddrinfo = socket.getaddrinfo
            socket.getaddrinfo = _patched_getaddrinfo


def uninstall() -> None:
    """Restore the system resolver (used by tests)."""
    global _orig_getaddrinfo
    with _lock:
        if _orig_getaddrinfo is not None:
            socket.getaddrinfo = _orig_getaddrinfo
            _orig_getaddrinfo = None
        _hosts.clear()
        _cache.clear()
