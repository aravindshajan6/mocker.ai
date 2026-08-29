from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import clear_auth_cookie, create_token, current_user, hash_password, set_auth_cookie, verify_password
from ..db import get_db
from ..models import User, UserPrefs, UserStats
from ..schemas import LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
async def register(data: RegisterIn, response: Response, db: AsyncSession = Depends(get_db)):
    email = data.email.lower()
    exists = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, name=data.name.strip(), password_hash=hash_password(data.password))
    user.stats = UserStats()
    db.add(user)
    await db.flush()
    # Reminders are opt-out, so the preference row has to exist from the start — otherwise the
    # reminder job's join silently skips everyone who never opened Settings.
    db.add(UserPrefs(user_id=user.id))
    await db.commit()
    set_auth_cookie(response, create_token(user.id))
    return UserOut(id=user.id, name=user.name, email=user.email)


@router.post("/login", response_model=UserOut)
async def login(data: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == data.email.lower()))).scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    set_auth_cookie(response, create_token(user.id))
    return UserOut(id=user.id, name=user.name, email=user.email)


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return UserOut(id=user.id, name=user.name, email=user.email)
