from __future__ import annotations

import asyncio
import datetime as dt
import os
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import Date, String, Time, and_, create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from thefuzz import fuzz, process

from .settings import settings

# DB setup


class Base(DeclarativeBase):
    pass


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[Optional[str]] = mapped_column(String)
    teacher: Mapped[Optional[str]] = mapped_column(String)
    room: Mapped[Optional[str]] = mapped_column(String)
    lesson_type: Mapped[Optional[str]] = mapped_column(String)
    start_time: Mapped[Optional[dt.time]] = mapped_column(Time)
    end_time: Mapped[Optional[dt.time]] = mapped_column(Time)
    date: Mapped[Optional[dt.date]] = mapped_column(Date)


_engine: Optional[Engine] = None


def _engine_lazy() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    dsn = None

    if hasattr(settings, "DB_DSN"):
        try:
            dsn = settings.DB_DSN
        except Exception:
            dsn = None

    if not dsn:
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        host = os.getenv("POSTGRES_HOST", "postgres")
        db = os.getenv("POSTGRES_DB", "schedule")
        if password:
            dsn = f"postgresql+psycopg2://{user}:{password}@{host}/{db}"
        else:
            dsn = f"postgresql+psycopg2://{user}@{host}/{db}"

    _engine = create_engine(dsn, pool_pre_ping=True, future=True)
    return _engine


# Helpers

_norm_re = re.compile(r"[^a-zа-яе\s]+", flags=re.IGNORECASE)


def norm(s: str) -> str:
    s = (s or "").lower().replace("е", "е")
    s = _norm_re.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def teacher_variants(raw: str) -> List[str]:
    n = norm(raw)
    parts = n.split()
    variants = {n}
    if parts:
        variants.add(parts[0])
    return list(variants)


def _subj_clean(s: str) -> str:
    return re.sub(r"\s*вебинар\s*:\s*\S+\s*$", "", s or "", flags=re.IGNORECASE).strip()


# DB queries


def _q_distinct_teachers_sync() -> List[str]:
    eng = _engine_lazy()
    today = dt.date.today()
    with Session(eng) as session:
        stmt = (
            select(func.distinct(Lesson.teacher))
            .where(
                and_(
                    Lesson.date >= today,
                    Lesson.teacher.is_not(None),
                    func.trim(Lesson.teacher) != "",
                )
            )
            .order_by(Lesson.teacher)
        )
        return [row[0] for row in session.execute(stmt) if row[0]]


def _q_overview_sync() -> Dict[str, List[str]]:
    eng = _engine_lazy()
    today = dt.date.today()
    with Session(eng) as session:
        stmt = (
            select(Lesson.teacher, Lesson.subject)
            .where(
                and_(
                    Lesson.date >= today,
                    Lesson.teacher.is_not(None),
                    func.trim(Lesson.teacher) != "",
                    Lesson.subject.is_not(None),
                    func.trim(Lesson.subject) != "",
                )
            )
            .order_by(Lesson.teacher, Lesson.subject)
        )
        out: Dict[str, List[str]] = defaultdict(list)
        seen = set()
        for teacher, subject in session.execute(stmt):
            key = (teacher, subject)
            if key in seen or not teacher or not subject:
                continue
            seen.add(key)
            out[teacher].append(subject)
        return out


def _q_teacher_timetable_sync(
    teacher_exact: str,
) -> List[Tuple[dt.date, str, str, str, str]]:
    eng = _engine_lazy()
    today = dt.date.today()
    with Session(eng) as session:
        stmt = (
            select(
                Lesson.date,
                func.to_char(Lesson.start_time, "HH24:MI"),
                func.to_char(Lesson.end_time, "HH24:MI"),
                Lesson.subject,
                func.coalesce(Lesson.room, ""),
            )
            .where(
                and_(
                    Lesson.date >= today,
                    func.lower(func.replace(Lesson.teacher, "е", "Е")).like(
                        func.lower(func.replace(teacher_exact, "е", "Е"))
                    ),
                )
            )
            .order_by(Lesson.date, Lesson.start_time)
        )
        rows = list(session.execute(stmt))
        if not rows:
            stmt2 = (
                select(
                    Lesson.date,
                    func.to_char(Lesson.start_time, "HH24:MI"),
                    func.to_char(Lesson.end_time, "HH24:MI"),
                    Lesson.subject,
                    func.coalesce(Lesson.room, ""),
                )
                .where(and_(Lesson.date >= today, Lesson.teacher == teacher_exact))
                .order_by(Lesson.date, Lesson.start_time)
            )
            rows = list(session.execute(stmt2))

        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]


# Public API


async def _fetch_distinct_teachers() -> List[str]:
    return await asyncio.to_thread(_q_distinct_teachers_sync)


async def _fetch_overview() -> Dict[str, List[str]]:
    return await asyncio.to_thread(_q_overview_sync)


async def _fetch_timetable_for_teacher(
    raw_teacher: str,
) -> List[Tuple[dt.date, str, str, str, str]]:
    return await asyncio.to_thread(_q_teacher_timetable_sync, raw_teacher)


async def teachers_overview() -> str:
    data = await _fetch_overview()
    if not data:
        return "Не нашел преподавателей в будущих занятиях."

    lines = ["Преподаватели (из будущих занятий):"]
    for teacher, subjects in sorted(data.items(), key=lambda kv: kv[0]):
        subj_line = ", ".join(sorted({_subj_clean(s) for s in subjects}))
        lines.append(f"{teacher} — {subj_line}")
    return "\n".join(lines)


async def teacher_timetable(query: str) -> str:
    query = (query or "").strip()
    if not query:
        return "Укажите фамилию или ФИО преподавателя."

    teachers = await _fetch_distinct_teachers()
    if not teachers:
        return "В базе сейчас нет будущих занятий."

    candidate_list: List[str] = []
    back_map: Dict[str, str] = {}
    for t in teachers:
        for v in teacher_variants(t):
            candidate_list.append(v)
            back_map[v] = t

    qn = norm(query)

    best = process.extractOne(qn, candidate_list, scorer=fuzz.WRatio)
    if not best or best[1] < 70:
        hints_raw = process.extract(qn, candidate_list, limit=5, scorer=fuzz.WRatio)
        hints = [back_map[h[0]] for h in hints_raw if h[1] >= 55]
        hints = list(dict.fromkeys(hints))[:3]  # dedup & trim
        if hints:
            return (
                "Не нашел точного совпадения.\nВозможно, вы имели в виду:\n• "
                + "\n• ".join(hints)
            )
        return "Не нашел такого преподавателя. Попробуйте еще раз "

    matched_teacher = back_map[best[0]]

    rows = await _fetch_timetable_for_teacher(matched_teacher)
    if not rows:
        return f"Занятий для «{matched_teacher}» впереди не нашлось."

    def dow(d: dt.date) -> str:
        names = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
        return names[d.weekday()]

    lines = [f"Расписание для {matched_teacher}:"]
    for d, s, e, subj, room in rows:
        subj_clean = _subj_clean(subj or "")
        tail = f" ({room})" if room and room.strip() else ""
        lines.append(f"{d.strftime('%d.%m')} ({dow(d)}) {s}–{e} — {subj_clean}{tail}")

    return "\n".join(lines)
