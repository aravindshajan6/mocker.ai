"""Rate limiting, and working out who the client actually is.

Behind a reverse proxy `request.client.host` is the proxy, not the visitor. If that is used as the
rate-limit key, every visitor shares one bucket: the first few failed logins lock out the world.
So the client IP is recovered from X-Forwarded-For — but only by trusting a known number of hops.

Why a count rather than "take the first entry": X-Forwarded-For is client-supplied and appended to
by each proxy, so the leftmost value is whatever the caller put there. Trusting it lets anyone
forge an IP and get a fresh bucket per request, which is the same as having no limiter. Counting
back from the right skips exactly the proxies we control and lands on the entry the outermost
trusted proxy wrote, which the client cannot influence.

The count must match the real topology. Here that is Traefik -> Next.js rewrite -> uvicorn, and the
value is verified by test (see tests/test_ratelimit.py) rather than assumed.
"""
from __future__ import annotations

import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ..config import settings

log = logging.getLogger("ratelimit")


def client_ip(request: Request) -> str:
    """The visitor's IP, as written by the outermost proxy we trust."""
    hops = max(0, settings.trusted_proxy_hops)
    if hops:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                # With `hops` proxies in front, the visitor is `hops` from the right. Anything
                # further left was supplied by the caller and cannot be trusted.
                return parts[-hops] if len(parts) >= hops else parts[0]
    return get_remote_address(request) or "unknown"


limiter = Limiter(
    key_func=client_ip,
    default_limits=[settings.rate_limit_default],
    headers_enabled=True,          # sends Retry-After and X-RateLimit-* so clients can behave
    enabled=settings.rate_limit_enabled,
)


async def too_many_requests(request: Request, exc: RateLimitExceeded):
    """A plain, non-leaky message. Never say which limit or how many attempts remain."""
    from fastapi.responses import JSONResponse

    log.info("rate limited %s on %s", client_ip(request), request.url.path)
    # slowapi's exception carries the Limit, not a retry time; the window length is the honest
    # answer and comes off the underlying limits item. Its own `detail` is the limit string
    # ("8 per 1 minute"), which is why the body below is replaced rather than passed through.
    window = 60
    try:
        window = int(exc.limit.limit.get_expiry())
    except Exception:  # noqa: BLE001 - never fail a 429 over a header
        pass
    headers = {"Retry-After": str(window)}
    return JSONResponse(
        {"detail": "Too many requests. Please wait a moment and try again."},
        status_code=429, headers=headers,
    )
