import typer
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import subprocess, signal, os
from schedule_vvsu.config import settings
from schedule_vvsu.google_calendar.auth import authenticate_google_calendar
from schedule_vvsu.google_calendar.calendar import list_calendars, remove_calendar

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
        typer.echo("w")
        return

    # Посылаем сигнал SIGTERM
    scheduler_process.terminate()
    typer.echo("Scheduler остановлен.")
    logger.info("Scheduler остановлен.")


def main():
    """
    Точка входа в CLI.
    """
    logger.info("Запуск CLI для управления календарями.")
    app()


if __name__ == "__main__":
    main()
