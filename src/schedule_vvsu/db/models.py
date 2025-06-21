from datetime import datetime as dt_datetime, date as dt_date, time as dt_time
from typing import Optional

from sqlalchemy import Column, Date, DateTime, Integer, String, Time, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class LogEntry(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timestamp: Mapped[dt_datetime] = mapped_column(DateTime, server_default=func.now())
    level: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    teacher: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    room: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lesson_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    start_time: Mapped[dt_time] = mapped_column(Time, nullable=False)
    end_time: Mapped[dt_time] = mapped_column(Time, nullable=False)
    date: Mapped[dt_date] = mapped_column(Date, nullable=False)
    group: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    updated_at: Mapped[dt_datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ExcludedLesson(Base):
    __tablename__ = "excluded_lessons"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    teacher: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    weekday: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    start_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class SchedulerStatus(Base):
    __tablename__ = "scheduler_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[dt_datetime] = mapped_column(DateTime, default=dt_datetime.utcnow)


class ParseRun(Base):
    __tablename__ = "parse_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    time_str: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timestamp: Mapped[dt_datetime] = mapped_column(DateTime, default=dt_datetime.utcnow)


@event.listens_for(Setting, "after_insert")
@event.listens_for(Setting, "after_update")
def _notify_bot(mapper, connection, target):
    """Отправляем NOTIFY на изменение конфигурации бота."""
    if target.key in ("BOT_TOKEN", "ADMIN_IDS", "BOT_ENABLED"):
        connection.exec_driver_sql("NOTIFY bot_config, 'reload';")


from passlib.hash import bcrypt


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[dt_datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # метод-хелпер для проверки пароля
    def verify(self, raw: str) -> bool:
        return bcrypt.verify(raw, self.password_hash)
