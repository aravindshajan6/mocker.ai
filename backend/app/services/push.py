"""Web Push notifications.

Chosen as the default reminder channel because it needs no third-party account: the server
generates its own VAPID keypair on first boot and talks directly to the browser's push service.
Telegram is offered as an alternative when a bot token is configured.

Reach is honest but limited: Android Chrome works from an ordinary tab, while iOS Safari only
delivers to a site the user has added to their Home Screen (which is why the app ships a PWA
manifest). Opt-in rates for web push are typically single digits, so this is a bonus channel,
never the only way the app communicates.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01
from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import AppConfig, PushSubscription

log = logging.getLogger("push")

PRIVATE_KEY = "vapid_private_pem"
PUBLIC_KEY = "vapid_public_b64"
MAX_FAILURES = 3


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


async def ensure_keys(db: AsyncSession) -> tuple[str, str]:
    """Return (private PEM, public application-server key), generating them once and persisting."""
    priv = await db.get(AppConfig, PRIVATE_KEY)
    pub = await db.get(AppConfig, PUBLIC_KEY)
    if priv and pub:
        return priv.value, pub.value

    v = Vapid01()
    v.generate_keys()
    pem = v.private_pem()
    if isinstance(pem, bytes):
        pem = pem.decode()
    raw_public = v.public_key.public_bytes(serialization.Encoding.X962,
                                           serialization.PublicFormat.UncompressedPoint)
    public_b64 = _b64(raw_public)
    db.add(AppConfig(key=PRIVATE_KEY, value=pem))
    db.add(AppConfig(key=PUBLIC_KEY, value=public_b64))
    await db.commit()
    log.info("generated a VAPID keypair for web push")
    return pem, public_b64


async def public_key(db: AsyncSession) -> str:
    _, pub = await ensure_keys(db)
    return pub


def _send(private_pem: str, sub: PushSubscription, payload: dict) -> tuple[bool, bool]:
    """Returns (delivered, should_drop_subscription)."""
    try:
        webpush(
            subscription_info={"endpoint": sub.endpoint,
                               "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
            data=json.dumps(payload),
            vapid_private_key=private_pem,
            vapid_claims={"sub": settings.vapid_subject},
            timeout=10,
        )
        return True, False
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        # 404/410 mean the browser threw the subscription away; anything else may be transient.
        if status in (404, 410):
            return False, True
        log.warning("web push failed (%s): %s", status, e)
        return False, False
    except Exception as e:  # noqa: BLE001
        log.warning("web push error: %s", e)
        return False, False


async def send_to_user(db: AsyncSession, user_id: str, payload: dict) -> int:
    """Push to every device this user has registered. Returns how many were delivered."""
    private_pem, _ = await ensure_keys(db)
    subs = (await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))).scalars().all()
    delivered = 0
    for sub in subs:
        # pywebpush is synchronous; the reminder pass iterates every due user, so this must not
        # hold the event loop while each provider round-trip completes.
        ok, drop = await asyncio.to_thread(_send, private_pem, sub, payload)
        if ok:
            delivered += 1
            sub.failures = 0
        elif drop:
            await db.delete(sub)
        else:
            sub.failures += 1
            if sub.failures >= MAX_FAILURES:
                await db.delete(sub)
    await db.commit()
    return delivered
