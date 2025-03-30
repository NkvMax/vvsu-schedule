import typer
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import subprocess, signal, os
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from schedule_vvsu.config import settings
from schedule_vvsu.google_calendar.auth import authenticate_google_calendar
from schedule_vvsu.google_calendar.calendar import list_calendars, remove_calendar, get_or_create_calendar
from schedule_vvsu.google_calendar.sync import sync_schedule_to_calendar
from schedule_vvsu.parser import parse_schedule, save_to_json
from typing import Optional

# Настройка логирования
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_handler = TimedRotatingFileHandler(
    filename=LOG_DIR / "cli_actions.log",
    when="midnight",
    interval=1,
    backupCount=7
)
log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s:%(message)s"))
logger = logging.getLogger("cli_logger")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

# Создаем Typer-приложение
app = typer.Typer()

# scheduler_process: Optional[subprocess.Popen] = None
scheduler_process = None  # Глобальная переменная для хранения PID процесса


@app.command()
def list_all():
    """
    Показывает все доступные календари (сервисного или пользовательского аккаунта,
    в зависимости от ACCOUNT_TYPE в настройках).
    """
    logger.info("Запуск команды list_all() для вывода календарей")
    service = authenticate_google_calendar()
    cals = list_calendars(service)
    if not cals:
        typer.echo("Нет доступных календарей.")
        return
    typer.echo("Список календарей:")
    for cal in cals:
        typer.echo(f" - {cal.get('summary')} (ID: {cal.get('id')})")


@app.command()
def rm(calendar_id: str):
    """
    Удаляет календарь по заданному ID.
    """
    logger.info(f"Запуск команды rm() для удаления календаря {calendar_id}")
    service = authenticate_google_calendar()
    confirm = typer.confirm(f"Вы действительно хотите удалить календарь с ID: {calendar_id}?")
    if confirm:
        remove_calendar(service, calendar_id)
        typer.echo("Календарь удалeн.")
        logger.info(f"Календарь {calendar_id} удалeн.")
    else:
        typer.echo("Операция отменена.")
        logger.info("Удаление календаря отменено пользователем.")


@app.command()
def start_scheduler():
    """
    Запускает APScheduler (из src/scheduler.py) в отдельном процессе.
    """
    logger.info("Команда start_scheduler()")
    global scheduler_process
    if scheduler_process and scheduler_process.poll() is None:
        typer.echo("Scheduler уже запущен.")
        return

    # Запускаем как отдельный процесс: "python -m src.scheduler"
    cmd = ["python", "-m", "schedule_vvsu.scheduler"]
    scheduler_process = subprocess.Popen(cmd)
    typer.echo(f"Scheduler запущен, PID={scheduler_process.pid}")
    logger.info(f"Scheduler запущен, PID={scheduler_process.pid}")


@app.command()
def stop_scheduler():
    """
    Останавливает APScheduler-процесс (если он запущен).
    """
    logger.info("Команда stop_scheduler()")
    global scheduler_process
    if not scheduler_process or scheduler_process.poll() is not None:
        typer.echo("Scheduler уже остановлен.")
        return

    # Посылаем сигнал SIGTERM
    scheduler_process.terminate()
    scheduler_process.wait()
    logger.info("Scheduler остановлен.")
    typer.echo("Scheduler остановлен.")


@app.command()
def sync_now():
    """
    Немедленно запускает синхронизацию расписания с Google Calendar.
    """
    logger.info("Запуск немедленной синхронизации расписания.")
    schedule = parse_schedule()
    if not schedule:
        logger.error("Не удалось получить расписание.")
        return

    save_to_json(schedule)
    service = authenticate_google_calendar()
    calendar_name = settings.CALENDAR_NAME  # Название календаря
    calendar_id = get_or_create_calendar(service, calendar_name)
    sync_schedule_to_calendar(service, schedule, calendar_id)
    logger.info("Синхронизация завершена успешно.")
    print("Синхронизация завершена успешно.")


def job():
    print(f"[{datetime.now()}] Запускается задача синхронизации.")
    schedule = parse_schedule()
    if schedule:
        save_to_json(schedule)
        service = authenticate_google_calendar()
        calendar_name = settings.CALENDAR_NAME
        calendar_id = get_or_create_calendar(service, calendar_name)
        sync_schedule_to_calendar(service, schedule, calendar_id)
        print(f"[{datetime.now()}] Задача синхронизации завершена.")
    else:
        logging.error("Не удалось получить расписание.")


def main():
    scheduler = BlockingScheduler()

    intervals = settings.PARSING_INTERVALS.split(",")
    for interval in intervals:
        hour, minute = map(int, interval.strip().split(":"))
        scheduler.add_job(job, 'cron', hour=hour, minute=minute)
        print(f"Задача добавлена на запуск в {hour:02d}:{minute:02d}.")

    print("Планировщик запущен и ожидает задач.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Планировщик остановлен.")
