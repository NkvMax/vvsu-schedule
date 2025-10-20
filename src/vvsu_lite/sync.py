import argparse, logging, os
from typing import List
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)
except Exception:
    pass

from vvsu_lite.parser import fetch_lessons
from vvsu_lite.dto import Lesson

def get_logger() -> logging.Logger:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | vvsu-lite | %(message)s")
    return logging.getLogger("vvsu-lite")

def to_lessons(items):
    return [Lesson(
        date=i["date"],
        time_range=i["time_range"],
        discipline=i["discipline"],
        lesson_type=i.get("lesson_type",""),
        auditorium=i.get("auditorium",""),
        teacher=i.get("teacher",""),
        webinar_url=i.get("webinar_url"),
    ) for i in items]

def main(dry_run: bool):
    logger = get_logger()
    logger.info("VVSU Lite start (dry_run=%s)", dry_run)

    lessons_raw = fetch_lessons(logger)
    lessons = to_lessons(lessons_raw)
    logger.info("Итого занятий: %d", len(lessons))

    if dry_run:
        for ls in lessons:
            if ls.webinar_url:
                logger.info("DRY-RUN: %s (webinar_url=%s)", ls, ls.webinar_url)
            else:
                logger.info("DRY-RUN: %s", ls)
        logger.info("DRY-RUN complete")
        return

    # Google Calendar sync
    from vvsu_lite.google_calendar.client import load_service, find_calendar_id, share_calendar_if_needed
    from vvsu_lite.google_calendar.syncer import upsert_to_calendar

    cal_summary = os.getenv("GCAL_CALENDAR_SUMMARY", "").strip()
    cal_id_env = os.getenv("GCAL_CALENDAR_ID", "").strip()

    service = load_service(logger)
    cal_id = find_calendar_id(service, logger, cal_summary, cal_id_env)
    logger.info("Используем календарь: id=%s; summary=%s", cal_id, cal_summary or "(by-id)")
    share_calendar_if_needed(service, cal_id, logger)

    upsert_to_calendar(service, cal_id, lessons, logger)

def cli():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    main(dry_run=args.dry_run)

if __name__ == "__main__":
    cli()
