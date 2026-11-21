import json
import socket

import pytest

from mats.net import dns


def _answer(*ips: str, ttl: int = 300) -> bytes:
    recs = [{"name": "x", "type": 5, "TTL": ttl, "data": "cdn.example."}]
    recs += [{"name": "x", "type": 1, "TTL": ttl, "data": ip} for ip in ips]
    return json.dumps({"Status": 0, "Answer": recs}).encode()


@pytest.fixture(autouse=True)
def _clean():
    dns.uninstall()
    yield
    dns.uninstall()


def test_parse_doh_skips_cname_and_bad_records() -> None:
    body = json.dumps(
        {"Answer": [{"type": 5, "data": "a."}, {"type": 1, "TTL": 30, "data": "1.2.3.4"},
                    {"type": 1, "data": "not-an-ip"}]}
    ).encode()
    ips, ttl = dns.parse_doh(body)
    assert ips == ["1.2.3.4"]
    assert ttl == 60.0  # floored


def test_resolve_caches_until_ttl() -> None:
    calls = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return _answer("9.9.9.9", ttl=120)

    t = [1000.0]
    assert dns.resolve("fapi.binance.com", fetch, lambda: t[0]) == ["9.9.9.9"]
    assert dns.resolve("fapi.binance.com", fetch, lambda: t[0] + 100) == ["9.9.9.9"]
    assert len(calls) == 1
    dns.resolve("fapi.binance.com", fetch, lambda: t[0] + 200)
    assert len(calls) == 2


def test_resolve_falls_through_to_second_endpoint() -> None:
    def fetch(url: str) -> bytes:
        if "cloudflare" in url:
            raise OSError("down")
        return _answer("8.8.4.4")

    assert dns.resolve("fapi.binance.com", fetch) == ["8.8.4.4"]


def test_install_routes_only_listed_hosts(monkeypatch) -> None:
    seen = []

    def fake_orig(host, port, family=0, type=0, proto=0, flags=0):
        seen.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_orig)
    monkeypatch.setattr(dns, "resolve", lambda h: ["5.6.7.8"])
    dns.install({"fapi.binance.com"})
    socket.getaddrinfo("fapi.binance.com", 443)
    socket.getaddrinfo("api.bybit.com", 443)
    assert seen == ["5.6.7.8", "api.bybit.com"]


def test_install_falls_back_to_system_when_doh_fails(monkeypatch) -> None:
    seen = []
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, port, *a, **k: seen.append(host) or [(socket.AF_INET, 1, 6, "", (host, port))],
    )
    monkeypatch.setattr(dns, "resolve", lambda h: [])
    dns.install({"fapi.binance.com"})
    socket.getaddrinfo("fapi.binance.com", 443)
    assert seen == ["fapi.binance.com"]
