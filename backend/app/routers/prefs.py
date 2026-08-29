"""Reminder settings, push subscriptions and Telegram linking."""
from __future__ import annotations

from zoneinfo import ZoneInfo, available_timezones

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..config import settings
from ..db import get_db
from ..models import PushSubscription, User, UserPrefs
from ..schemas import PrefsIn, PrefsOut, PushSubscribeIn
from ..services import push, telegram

router = APIRouter(prefix="/api/me", tags=["prefs"])


async def get_prefs(db: AsyncSession, user_id: str) -> UserPrefs:
    p = await db.get(UserPrefs, user_id)
    if not p:
        p = UserPrefs(user_id=user_id)
        db.add(p)
        await db.commit()
    return p


async def _out(db: AsyncSession, user: User, p: UserPrefs) -> PrefsOut:
    devices = (await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user.id)
    )).scalars().all()
    return PrefsOut(
        reminders_enabled=p.reminders_enabled, reminder_hour=p.reminder_hour,
        reminder_minute=p.reminder_minute, timezone=p.timezone,
        push_devices=len(devices), vapid_public_key=await push.public_key(db),
        telegram_linked=bool(p.telegram_chat_id), telegram_available=telegram.configured(),
        telegram_link_url=telegram.deep_link(p.telegram_link_code) if p.telegram_link_code else None,
    )


@router.get("/prefs", response_model=PrefsOut)
async def read_prefs(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await _out(db, user, await get_prefs(db, user.id))


@router.put("/prefs", response_model=PrefsOut)
async def update_prefs(data: PrefsIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    p = await get_prefs(db, user.id)
    if data.timezone is not None:
        if data.timezone not in available_timezones():
            raise HTTPException(422, "Unknown timezone")
        p.timezone = data.timezone
    if data.reminders_enabled is not None:
        p.reminders_enabled = data.reminders_enabled
    if data.reminder_hour is not None:
        p.reminder_hour = data.reminder_hour
    if data.reminder_minute is not None:
        p.reminder_minute = data.reminder_minute
    await db.commit()
    return await _out(db, user, p)


@router.post("/push/subscribe", response_model=PrefsOut)
async def subscribe(data: PushSubscribeIn, user: User = Depends(current_user),
                    db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == data.endpoint)
    )).scalar_one_or_none()
    if existing:
        existing.user_id, existing.p256dh, existing.auth, existing.failures = user.id, data.p256dh, data.auth, 0
    else:
        db.add(PushSubscription(user_id=user.id, endpoint=data.endpoint, p256dh=data.p256dh, auth=data.auth))
    await db.commit()
    return await _out(db, user, await get_prefs(db, user.id))


@router.post("/push/unsubscribe", response_model=PrefsOut)
async def unsubscribe(data: PushSubscribeIn, user: User = Depends(current_user),
                      db: AsyncSession = Depends(get_db)):
    sub = (await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == data.endpoint,
                                       PushSubscription.user_id == user.id)
    )).scalar_one_or_none()
    if sub:
        await db.delete(sub)
        await db.commit()
    return await _out(db, user, await get_prefs(db, user.id))


@router.post("/push/test")
async def test_push(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    sent = await push.send_to_user(db, user.id, {
        "title": "Mocker reminder test",
        "body": "This is what your daily nudge will look like.",
        "url": "/",
    })
    if not sent:
        raise HTTPException(409, "No device is subscribed to notifications yet")
    return {"delivered": sent}


@router.post("/telegram/link", response_model=PrefsOut)
async def telegram_link(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if not telegram.configured():
        raise HTTPException(503, "Telegram reminders are not configured on this server")
    p = await get_prefs(db, user.id)
    p.telegram_link_code = telegram.new_link_code()
    await db.commit()
    return await _out(db, user, p)


@router.post("/telegram/unlink", response_model=PrefsOut)
async def telegram_unlink(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    p = await get_prefs(db, user.id)
    p.telegram_chat_id = None
    p.telegram_link_code = None
    await db.commit()
    return await _out(db, user, p)
