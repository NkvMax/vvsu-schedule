import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from schedule_vvsu.logs.db_logger import DBLogHandler

_initialized = False


def setup_logging():
    global _initialized
    if _initialized:
        return

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    LOG_DIR = BASE_DIR / "logs"
    LOG_DIR.mkdir(exist_ok=True)

    file_handler = TimedRotatingFileHandler(
        filename=LOG_DIR / "sync_log.log",
        when="midnight",
        interval=1,
        backupCount=7
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))

    if not any(isinstance(h, TimedRotatingFileHandler) for h in logger.handlers):
        logger.addHandler(file_handler)

    db_handler = DBLogHandler()
    db_handler.setLevel(logging.INFO)
    db_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))

    if not any(isinstance(h, DBLogHandler) for h in logger.handlers):
        logger.addHandler(db_handler)

    _initialized = True  # пометка, что уже настроен
