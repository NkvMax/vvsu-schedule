import typer
import logging
import subprocess
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler

from schedule_vvsu.config import get_settings
from schedule_vvsu.google_calendar.auth import authenticate_google_calendar
from schedule_vvsu.google_calendar.calendar import list_calendars, remove_calendar, get_or_create_calendar
from schedule_vvsu.google_calendar.sync import sync_schedule_to_calendar
from schedule_vvsu.parser import parse_schedule
from schedule_vvsu.database import init_db, save_lessons_to_db, Base, engine
from schedule_vvsu.logs.logger_setup import setup_logging

# Инициализация настроек
settings = get_settings()

# Создаем таблицы если не созданы
Base.metadata.create_all(bind=engine)

# Настройка логирования
setup_logging()
logger = logging.getLogger("cli_logger")

# Typer-приложение
app = typer.Typer()

# PID процесса планировщика
scheduler_process: Optional[subprocess.Popen] = None


@app.command()
def list_all():
    """
    Показывает все календари текущего аккаунта (user/service).
    """
    logger.info("Команда list_all()")
    service = authenticate_google_calendar()
    calendars = list_calendars(service)
    if not calendars:
        typer.echo("Нет доступных календарей.")
        return
    typer.echo("Календари:")
    for cal in calendars:
        typer.echo(f" - {cal.get('summary')} (ID: {cal.get('id')})")


@app.command()
def rm(calendar_id: str):
    """
    Удаляет календарь по его ID.
    """
    logger.info(f"Команда rm() для ID: {calendar_id}")
    service = authenticate_google_calendar()
    if typer.confirm(f"Удалить календарь с ID: {calendar_id}?"):
        remove_calendar(service, calendar_id)
        typer.echo("Календарь удален.")
        logger.info(f"Календарь с ID: {calendar_id} удален успешно")
    else:
        typer.echo("Операция отменена.")
        logger.info("Операция удаления была отменена")


@app.command()
def start_scheduler():
    """
    Запускает планировщик в отдельном процессе.
    """
    logger.info("Планировщик запустился")
    global scheduler_process
    if scheduler_process and scheduler_process.poll() is None:
        typer.echo("Планировщик уже запущен.")
        return

    cmd = ["python", "-m", "schedule_vvsu.scheduler"]
    scheduler_process = subprocess.Popen(cmd)
    typer.echo(f"Планировщик запущен, PID={scheduler_process.pid}")
    logger.info(f"Планировщик запущен, PID={scheduler_process.pid}")


@app.command()
def stop_scheduler():
    """
    Останавливает планировщик (если запущен).
    """
    logger.info("Планировщик был остановлен")
    global scheduler_process
    if not scheduler_process or scheduler_process.poll() is not None:
        typer.echo("Планировщик уже остановлен.")
        return

    # Посылаем сигнал SIGTERM
    scheduler_process.terminate()
    scheduler_process.wait()
    typer.echo("Планировщик остановлен.")
    logger.info("Планировщик остановлен")


@app.command()
def sync_now():
    """
    Синхронизирует расписание с Google Календарем немедленно.
    """
    logger.info("Запуск немедленной синхронизации расписания.")
    init_db()
    schedule = parse_schedule()
    if not schedule:
        logger.error("Не удалось получить расписание с Google календаря.")
        return

    save_lessons_to_db(schedule)

    service = authenticate_google_calendar()
    calendar_id = get_or_create_calendar(service, settings.CALENDAR_NAME)
    sync_schedule_to_calendar(service, schedule, calendar_id)
    logger.info("Синхронизация завершена успешно.")
    typer.echo("Синхронизация завершена.")


@app.command()
def migrate():
    """
    Применяет все доступные миграции Alembic.
    """
    logger.info("Выполнение миграций Alembic")
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    logger.info("Миграции применены.")


def job():
    logger.info(f"[{datetime.now()}] Запуск задачи синхронизации.")
    init_db()
    schedule = parse_schedule()
    if schedule:
        save_lessons_to_db(schedule)
        service = authenticate_google_calendar()
        calendar_id = get_or_create_calendar(service, settings.CALENDAR_NAME)
        sync_schedule_to_calendar(service, schedule, calendar_id)
        logger.info(f"[{datetime.now()}] Задача синхронизации завершена.")
    else:
        logging.warning("Не удалось получить расписание.")


def main():
    init_db()
    Base.metadata.create_all(bind=engine)

    scheduler = BlockingScheduler()
    intervals = settings.PARSING_INTERVALS.split(",")
    for interval in intervals:
        hour, minute = map(int, interval.strip().split(":"))
        scheduler.add_job(job, 'cron', hour=hour, minute=minute)
        logger.info(f"Задача добавлена на запуск в {hour:02d}:{minute:02d}.")

    logger.info("Планировщик запущен и ожидает задач.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Планировщик остановлен.")
