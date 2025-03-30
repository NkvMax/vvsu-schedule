import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime

from schedule_vvsu.config import settings
from schedule_vvsu.google_calendar.auth import authenticate_google_calendar
from schedule_vvsu.google_calendar.calendar import get_or_create_calendar
from schedule_vvsu.google_calendar.sync import sync_schedule_to_calendar
from schedule_vvsu.parser import parse_schedule, save_to_json

# Загружаем переменные из .env
load_dotenv()

# Настраиваем логирование с ротацией файлов
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_handler = TimedRotatingFileHandler(
    filename=LOG_DIR / "sync_log.log",
    when="midnight",
    interval=1,
    backupCount=7
)
log_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s:%(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)


def sync_task():
    logger.info("Запуск задачи синхронизации расписания из личного кабинета.")
    try:
        schedule = parse_schedule()
        if not schedule:
            logger.error("Не удалось получить расписание.")
            return

        save_to_json(schedule)
        service = authenticate_google_calendar()
        calendar_name = settings.CALENDAR_NAME  # Название календаря в Google calendar
        calendar_id = get_or_create_calendar(service, calendar_name)
        sync_schedule_to_calendar(service, schedule, calendar_id)
        logger.info("Синхронизация завершена успешно.")
    except Exception as e:
        logger.exception(f"Произошла непредвиденная ошибка: {e}")


def main():
    if settings.DEV_MODE:
        logger.info("DEV_MODE включен. Парсинг запускается принудительно.")
        sync_task()
    else:
        # Если не в режиме разработки, используем APScheduler для планирования задач
        logger.info("Приложение ожидает указанного временного интервала для запуска")
        scheduler = BlockingScheduler(timezone=settings.TIMEZONE)
        # Предполагаем, что PARSING_INTERVALS задана как "9:00,14:00,17:00"
        intervals = [t.strip() for t in settings.PARSING_INTERVALS.split(",") if t.strip()]
        for interval in intervals:
            hour, minute = map(int, interval.split(":"))
            scheduler.add_job(sync_task, 'cron', hour=hour, minute=minute, id=f"sync_{hour}_{minute}")
            logger.info(f"Задача запланирована на {hour:02d}:{minute:02d}")
        try:
            logger.info("Запуск планировщика задач...")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Остановка планировщика задач.")


if __name__ == "__main__":
    main()
