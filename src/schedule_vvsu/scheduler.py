import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from dateutil import tz
from dotenv import load_dotenv

from schedule_vvsu.config import get_settings
from schedule_vvsu.database import (
    Base,
    SessionLocal,
    engine,
    get_setting,
    init_db,
    save_lessons_to_db,
)
from schedule_vvsu.db.models import ParseRun, SchedulerStatus
from schedule_vvsu.google_calendar.auth import authenticate_google_calendar
from schedule_vvsu.google_calendar.calendar import get_or_create_calendar
from schedule_vvsu.google_calendar.sync import sync_schedule_to_calendar
from schedule_vvsu.logs.logger_setup import setup_logging
from schedule_vvsu.parser import parse_schedule
from schedule_vvsu.services.settings_service import get_calendar_name

load_dotenv()

# Инициализация логирования
setup_logging()
logger = logging.getLogger(__name__)

# Настройки
settings = get_settings()
VLADIVOSTOK_TZ = tz.gettz("Asia/Vladivostok")


def record_scheduler_status(status: str):
    session = SessionLocal()
    try:
        session.add(SchedulerStatus(status=status, updated_at=datetime.utcnow()))
        session.commit()
    finally:
        session.close()


def record_parse_run(status: str, detail: str = "", time_str: Optional[str] = None):
    """Сохраняет результат очередного прогона парсера в parse_runs."""
    now_local = datetime.now(tz=VLADIVOSTOK_TZ)

    if time_str is None:
        time_str = now_local.strftime("%H:%M")

    session = SessionLocal()
    try:
        session.add(
            ParseRun(
                time_str=time_str,
                status=status,
                detail=detail,
                timestamp=now_local.replace(tzinfo=None),
            )
        )
        session.commit()
        logger.info(f"Run записан: {status} @ {time_str} ({detail[:50]})")
    finally:
        session.close()


def sync_task():
    from dateutil import tz

    tz_local = tz.gettz("Asia/Vladivostok")
    now_local = datetime.now(tz_local)

    logger.info("Запуск задачи синхронизации расписания из личного кабинета.")
    record_parse_run("started", "cron запуск", time_str=now_local.strftime("%H:%M"))

    try:
        # Создаем сессию базы данных
        with SessionLocal() as db:
            schedule = parse_schedule()
            if not schedule:
                msg = "Расписание не получено — возможно, недоступно"
                logger.warning(msg)
                record_parse_run("error", msg, time_str=now_local.strftime("%H:%M"))
                return

            save_lessons_to_db(schedule)
            service = authenticate_google_calendar()
            calendar_id = get_or_create_calendar(
                service, get_calendar_name(db)
            )  # Используем get_calendar_name
            sync_schedule_to_calendar(service, schedule, calendar_id)

            ok_msg = f"Синхронизировано {len(schedule)} занятий"
            logger.info(ok_msg)
            record_parse_run("success", ok_msg, time_str=now_local.strftime("%H:%M"))

    except Exception as e:
        err_msg = f"Ошибка: {e}"
        logger.exception(err_msg)
        record_parse_run("error", err_msg[:250], time_str=now_local.strftime("%H:%M"))


def main():
    # Создание таблиц
    init_db()
    Base.metadata.create_all(bind=engine)

    logger.info("Планировщик запускается согласно настройкам временных интервалов.")
    record_scheduler_status("started")

    scheduler = BlockingScheduler(timezone=settings.TIMEZONE)

    interval_str = get_setting("PARSING_INTERVALS") or "09:00"
    intervals = [t.strip() for t in interval_str.split(",") if t.strip()]

    for interval in intervals:
        hour, minute = map(int, interval.split(":"))
        scheduler.add_job(
            sync_task,
            trigger="cron",
            hour=hour,
            minute=minute,
            id=f"sync_{hour}_{minute}",
        )
        logger.info(f"Задача запланирована на {hour:02d}:{minute:02d}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Планировщик остановлен.")
        record_scheduler_status("stopped")


if __name__ == "__main__":
    main()
