import logging, sys, os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

def setup_logging():
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler(sys.stdout)], force=True)
    try:
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)
        fh = TimedRotatingFileHandler(log_dir / "sync.log", when="midnight", backupCount=7, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        logging.getLogger().addHandler(fh)
    except Exception:
        pass
