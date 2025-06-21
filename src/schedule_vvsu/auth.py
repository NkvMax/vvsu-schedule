from __future__ import annotations
from typing import Optional
from datetime import datetime, timedelta
from typing import Annotated

import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from passlib.hash import bcrypt
from pydantic import BaseModel
from sqlalchemy import select, func

from schedule_vvsu.database import get_db as get_session

from schedule_vvsu.db.models import Admin

SECRET = os.getenv("JWT_SECRET", "CHANGE_ME")
ACCESS_TTL_MINUTES = 30

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer()


# схемы
class Creds(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# helpers
def _make_jwt(uid: int) -> str:
    exp = datetime.utcnow() + timedelta(minutes=ACCESS_TTL_MINUTES)
    payload = {"sub": str(uid), "exp": exp}
    return jwt.encode(payload, SECRET, "HS256")


async def current_admin(
        token: Annotated[str, Depends(bearer)],
        session=Depends(get_session),
) -> Admin:
    try:
        payload = jwt.decode(token.credentials, SECRET, ["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    admin = session.get(Admin, int(payload["sub"]))
    if not admin:
        raise HTTPException(status_code=401, detail="Admin not found")
    return admin


# endpoints
@router.get("/needs_init", response_model=bool)
def needs_init(session=Depends(get_session)) -> bool:
    """Возвращает True, если таблица admins пуста (нужна регистрация)."""
    return session.scalar(select(func.count(Admin.id))) == 0


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: Creds, session=Depends(get_session)):
    """Разрешается ровно один раз — когда еще нет админа."""
    if not needs_init(session):
        raise HTTPException(status_code=403, detail="Admin already exists")

    admin = Admin(username=data.username, password_hash=bcrypt.hash(data.password))
    session.add(admin)
    session.commit()
    session.refresh(admin)

    return {"access_token": _make_jwt(admin.id)}


@router.post("/login", response_model=TokenOut)
def login(data: Creds, session=Depends(get_session)):
    admin = session.scalar(select(Admin).where(Admin.username == data.username))
    if not admin or not admin.verify(data.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return {"access_token": _make_jwt(admin.id)}


# helpers для API.py
def needs_init(session=Depends(get_session)) -> bool:
    """True, если таблица admins пуста (используется в корневом роуте)."""
    return session.scalar(select(func.count(Admin.id))) == 0


async def optional_admin(
        token: Annotated[Optional[str], Depends(bearer)],
        session=Depends(get_session),
) -> Optional[Admin]:
    """
    - Header отсутствует -> None
    - Токен битый        -> None
    - Токен валиден      -> Admin
    """
    if token is None:
        return None
    try:
        payload = jwt.decode(token.credentials, SECRET, ["HS256"])
        return session.get(Admin, int(payload["sub"]))
    except JWTError:
        return None
