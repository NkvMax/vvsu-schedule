from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from schedule_vvsu.db.base import Base
from schedule_vvsu.db.models import Lesson, LogEntry, Setting, SchedulerStatus, ParseRun
from schedule_vvsu.dto.models import Lesson as LessonDTO
from contextlib import contextmanager
from sqlalchemy.orm import Session
from schedule_vvsu.db.models import Admin

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://user:password@localhost/schedule")

# SQLAlchemy настройки
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db() -> "Generator[Session, None, None]":  # типизация для IDE
    """
    Зависимость FastAPI: дает открытый Session
    и гарантирует закрытие по завершении запроса.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_lessons_to_db(lessons: list[LessonDTO]):
    session = SessionLocal()
    try:
        session.query(Lesson).delete()
        for lesson in lessons:
            db_lesson = Lesson(
                subject=lesson.discipline,
                teacher=lesson.teacher,
                room=lesson.auditorium,
                lesson_type=lesson.lesson_type,
                start_time=lesson.get_start_end_times()[0],  # метод из DTO
                end_time=lesson.get_start_end_times()[1],
                date=lesson.get_date(),
                group=getattr(lesson, "group", None)
            )
            session.add(db_lesson)
        session.commit()
    finally:
        session.close()


def load_lessons_from_db() -> list[LessonDTO]:
    session = SessionLocal()
    try:
        db_lessons = session.query(Lesson).all()
        result = []
        for l in db_lessons:
            result.append(LessonDTO(
                date=l.date.strftime("%d.%m.%Y"),
                time_range=f"{l.start_time.strftime('%H:%M')}-{l.end_time.strftime('%H:%M')}",
                discipline=l.subject,
                teacher=l.teacher,
                lesson_type=l.lesson_type,
                auditorium=l.room
            ))
        return result
    finally:
        session.close()


def set_setting(key: str, value: str):
    session = SessionLocal()
    try:
        setting = session.query(Setting).filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            session.add(Setting(key=key, value=value))
        session.commit()
    finally:
        session.close()


def get_setting(key: str) -> str | None:
    session = SessionLocal()
    try:
        setting = session.query(Setting).filter_by(key=key).first()
        return setting.value if setting else None
    finally:
        session.close()
