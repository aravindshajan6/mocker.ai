"""Rate limiting, and the trusted-proxy hop count that makes it per-visitor.

The hop count is the whole game. Too low and a forged X-Forwarded-For buys a fresh bucket per
request; too high and every visitor collapses into one and the first few bad logins lock out the
world. These tests pin the behaviour at each setting rather than trusting the number.
"""
import pytest

from app.services import ratelimit


class FakeRequest:
    """Minimal stand-in: the resolver only reads headers and the peer address."""

    def __init__(self, xff: str | None = None, peer: str = "10.0.0.9"):
        self.headers = {"x-forwarded-for": xff} if xff else {}
        self.client = type("C", (), {"host": peer})()
        self.scope = {"type": "http", "client": (peer, 1234), "headers": []}


def resolve(xff, hops, peer="10.0.0.9", monkeypatch=None):
    monkeypatch.setattr(ratelimit.settings, "trusted_proxy_hops", hops)
    return ratelimit.client_ip(FakeRequest(xff, peer))


def test_direct_connection_uses_the_peer(monkeypatch):
    """hops=0 is the development case: no proxy, trust nothing from headers."""
    assert resolve(None, 0, peer="203.0.113.7", monkeypatch=monkeypatch) == "203.0.113.7"
    # even with a header present, hops=0 must ignore it
    assert resolve("1.2.3.4", 0, peer="203.0.113.7", monkeypatch=monkeypatch) == "203.0.113.7"


def test_one_hop_takes_the_only_entry(monkeypatch):
    assert resolve("203.0.113.7", 1, monkeypatch=monkeypatch) == "203.0.113.7"


def test_two_hops_is_the_production_topology(monkeypatch):
    """Traefik appends the visitor, the Next rewrite appends Traefik. Visitor is second from right."""
    assert resolve("203.0.113.7, 10.0.1.5", 2, monkeypatch=monkeypatch) == "203.0.113.7"


def test_a_forged_leading_entry_is_ignored_at_the_right_hop_count(monkeypatch):
    """The attack: put someone else's IP at the front of the header to get a clean bucket.

    With hops=2 the resolver counts from the right, so the forged value is skipped entirely.
    """
    forged = "1.1.1.1, 203.0.113.7, 10.0.1.5"
    assert resolve(forged, 2, monkeypatch=monkeypatch) == "203.0.113.7"
    assert resolve(forged, 2, monkeypatch=monkeypatch) != "1.1.1.1"


def test_trusting_the_leftmost_entry_would_be_exploitable(monkeypatch):
    """Documents why the resolver does not simply take parts[0]."""
    a = resolve("1.1.1.1, 203.0.113.7, 10.0.1.5", 2, monkeypatch=monkeypatch)
    b = resolve("2.2.2.2, 203.0.113.7, 10.0.1.5", 2, monkeypatch=monkeypatch)
    assert a == b, "a caller changing the leftmost value must not get a different bucket"


def test_two_different_visitors_get_different_keys(monkeypatch):
    """The property that matters: independent buckets per real visitor."""
    one = resolve("203.0.113.7, 10.0.1.5", 2, monkeypatch=monkeypatch)
    two = resolve("198.51.100.9, 10.0.1.5", 2, monkeypatch=monkeypatch)
    assert one != two and one == "203.0.113.7" and two == "198.51.100.9"


def test_a_short_header_does_not_crash(monkeypatch):
    """A request that skipped a proxy must degrade, not raise."""
    assert resolve("203.0.113.7", 2, monkeypatch=monkeypatch) == "203.0.113.7"
    assert resolve("", 2, peer="10.0.0.9", monkeypatch=monkeypatch) == "10.0.0.9"


def test_whitespace_and_empty_entries_are_tolerated(monkeypatch):
    assert resolve("  203.0.113.7 ,  10.0.1.5 ", 2, monkeypatch=monkeypatch) == "203.0.113.7"
    assert resolve("203.0.113.7, , 10.0.1.5", 2, monkeypatch=monkeypatch) == "203.0.113.7"


# --- live endpoint behaviour -------------------------------------------------

def test_login_is_rate_limited(client):
    """Brute force against the three provisioned accounts must not be free."""
    from app.config import settings

    if not settings.rate_limit_enabled:
        pytest.skip("rate limiting disabled in this environment")

    codes = []
    for _ in range(25):
        r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
        codes.append(r.status_code)
        if r.status_code == 429:
            break
    assert 429 in codes, f"login never rate limited after {len(codes)} attempts: {set(codes)}"
    limited = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    assert "too many" in limited.json()["detail"].lower()


def test_the_limit_response_leaks_nothing(client):
    """No hint about which limit was hit, how many attempts remain, or whether the user exists."""
    from app.config import settings

    if not settings.rate_limit_enabled:
        pytest.skip("rate limiting disabled")
    for _ in range(25):
        r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})
        if r.status_code == 429:
            body = r.json()["detail"].lower()
            assert "nobody@example.com" not in body
            for leak in ("limit", "attempt", "remaining", "bucket", "per minute"):
                assert leak not in body, f"429 body mentions {leak!r}: {body}"
            return
    pytest.skip("did not reach the limit in this run")
