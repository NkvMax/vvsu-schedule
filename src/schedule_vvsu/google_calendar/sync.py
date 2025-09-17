from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from datetime import time as dtime

import pytz

from schedule_vvsu.config import get_settings
from schedule_vvsu.database import (
    SessionLocal,
    load_lessons_from_db,
    save_lessons_to_db,
)
from schedule_vvsu.db.models import ExcludedLesson
from schedule_vvsu.dto.models import Lesson
from schedule_vvsu.google_calendar.events import (
    create_event,
    generate_lesson_key,
    update_event,
)

settings = get_settings()
logger = logging.getLogger(__name__)


def _is_past(lesson: Lesson) -> bool:
    tz = pytz.timezone(settings.TIMEZONE)
    start = lesson.get_start_end_times()[0]
    if isinstance(start, str):
        fmt = "%H:%M:%S" if start.count(":") == 2 else "%H:%M"
        dt = datetime.strptime(f"{lesson.date} {start}", f"%d.%m.%Y {fmt}")
    elif isinstance(start, dtime):
        d = datetime.strptime(lesson.date, "%d.%m.%Y").date()
        dt = datetime.combine(d, start)
    else:
        return False
    return tz.localize(dt) < datetime.now(tz)


def _find_event_by_key(service, calendar_id: str, key: str):
    resp = (
        service.events()
        .list(
            calendarId=calendar_id,
            privateExtendedProperty=f"lesson_key={key}",
            singleEvents=True,
        )
        .execute()
    )
    items = resp.get("items", [])
    return items[0] if items else None


def _find_event_by_time_and_title(service, calendar_id: str, lesson: Lesson):
    """Fallback: ищем событие без ключа по окну времени и summary."""
    tz = pytz.timezone(settings.TIMEZONE)
    date = datetime.strptime(lesson.date, "%d.%m.%Y").date()
    start_s, end_s = lesson.get_start_end_times()
    if isinstance(start_s, dtime):
        start_dt = datetime.combine(date, start_s)
        end_dt = datetime.combine(date, end_s)
    else:
        fmt = "%H:%M:%S" if start_s.count(":") == 2 else "%H:%M"
        start_dt = datetime.strptime(f"{lesson.date} {start_s}", f"%d.%m.%Y {fmt}")
        end_dt = datetime.strptime(f"{lesson.date} {end_s}", f"%d.%m.%Y {fmt}")
    start_iso = tz.localize(start_dt).isoformat()
    end_iso = tz.localize(end_dt).isoformat()

    expected_summary = (
        f"{lesson.discipline.split(' вебинар:')[0].strip()} ({lesson.lesson_type})"
    )
    resp = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_iso,
            timeMax=end_iso,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    items = resp.get("items", [])
    for e in items:
        if e.get("summary") == expected_summary:
            return e
    return None


def _filter_excluded(schedule: list[Lesson]) -> list[Lesson]:
    session = SessionLocal()
    try:
        ex = session.query(ExcludedLesson).all()
        out = []
        for l in schedule:
            skip = any(
                x.title == l.discipline
                and (x.teacher is None or x.teacher == l.teacher)
                and (x.weekday is None or x.weekday == l.weekday)
                and (x.start_time is None or x.start_time == l.start_time)
                for x in ex
            )
            if not skip:
                out.append(l)
        return out
    finally:
        session.close()


def sync_schedule_to_calendar(service, schedule: list[Lesson], calendar_id: str):
    """Main sync entry — idempotent; always keeps webinar URL in description."""
    # previous snapshot from DB
    try:
        prev = load_lessons_from_db()
        logger.info("Загружено предыдущее расписание из БД.")
    except Exception as e:
        logger.warning("Ошибка загрузки предыдущего расписания: %s", e)
        prev = []

    # 2) apply excludes
    schedule = _filter_excluded(schedule)

    # 3) compute keys
    key_of = lambda l: generate_lesson_key(l.dict())
    prev_keys = {key_of(l) for l in prev}
    curr_keys = {key_of(l) for l in schedule}
    added = [l for l in schedule if key_of(l) not in prev_keys]
    removed = [l for l in prev if key_of(l) not in curr_keys]
    common_keys = prev_keys & curr_keys

    logger.info("Добавлено занятий: %d", len(added))
    logger.info("Удалено занятий: %d", len(removed))

    # 4) first lesson of day for reminders
    sorted_sched = sorted(
        schedule, key=lambda l: (l.get_date(), l.get_start_end_times()[0])
    )
    day_min_starts = {}
    for l in sorted_sched:
        day = l.get_date()
        start_time, _ = l.get_start_end_times()
        start_str = start_time.strftime("%H:%M")
        if day not in day_min_starts or start_str < day_min_starts[day]:
            day_min_starts[day] = start_str

    def is_first_of_day(lesson: Lesson) -> bool:
        day = lesson.get_date()
        start_time, _ = lesson.get_start_end_times()
        lesson_start_str = start_time.strftime("%H:%M")
        return day in day_min_starts and lesson_start_str == day_min_starts[day]

    # 5) added (with adoption)
    for lesson in added:
        key = key_of(lesson)
        is_first = is_first_of_day(lesson)
        try:
            ev = _find_event_by_key(service, calendar_id, key)
            if not ev:
                ev = _find_event_by_time_and_title(service, calendar_id, lesson)
            if ev:
                ev.setdefault("extendedProperties", {}).setdefault("private", {})[
                    "lesson_key"
                ] = key
                update_event(service, calendar_id, ev, lesson, lesson_key=key)
                logger.info("Обновлено событие (усыновлено): %s", ev.get("summary"))
            else:
                body = create_event(
                    lesson.dict(), is_first_of_day=is_first, lesson_key=key
                )
                created = (
                    service.events().insert(calendarId=calendar_id, body=body).execute()
                )
                logger.info(
                    "Добавлено событие: %s (%s)",
                    created.get("summary"),
                    created["start"]["dateTime"],
                )
        except Exception as e:
            logger.error("Ошибка при добавлении/обновлении события: %s", e)

    # 6) delete future removed
    for lesson in removed:
        if _is_past(lesson):
            logger.info(
                "Пропущено удаление прошедшего события: %s %s",
                lesson.discipline,
                lesson.date,
            )
            continue
        key = key_of(lesson)
        try:
            resp = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    privateExtendedProperty=f"lesson_key={key}",
                    singleEvents=True,
                )
                .execute()
            )
            for ev in resp.get("items", []):
                service.events().delete(
                    calendarId=calendar_id, eventId=ev["id"]
                ).execute()
                logger.info("Удалено событие: %s", ev.get("summary"))
        except Exception as e:
            logger.error("Ошибка при удалении события: %s", e)

    # 7) update common
    tz = pytz.timezone(settings.TIMEZONE)
    update_time = datetime.now(tz).strftime("%m.%d в %H:%M")
    for lesson in schedule:
        key = key_of(lesson)
        if key not in common_keys:
            continue
        try:
            resp = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    privateExtendedProperty=f"lesson_key={key}",
                    singleEvents=True,
                )
                .execute()
            )
            items = resp.get("items", [])
            if not items:
                # try to find by time+title
                ev = _find_event_by_time_and_title(service, calendar_id, lesson)
                if ev:
                    ev.setdefault("extendedProperties", {}).setdefault("private", {})[
                        "lesson_key"
                    ] = key
                    update_event(service, calendar_id, ev, lesson, lesson_key=key)
                    logger.info(
                        "Обновлено событие (добавлен ключ): %s - Update: %s",
                        ev.get("summary"),
                        update_time,
                    )
                else:
                    is_first = is_first_of_day(lesson)
                    body = create_event(
                        lesson.dict(), is_first_of_day=is_first, lesson_key=key
                    )
                    created = (
                        service.events()
                        .insert(calendarId=calendar_id, body=body)
                        .execute()
                    )
                    logger.info(
                        "Воссоздано событие: %s (%s)",
                        created.get("summary"),
                        created["start"]["dateTime"],
                    )
            else:
                for ev in items:
                    update_event(service, calendar_id, ev, lesson, lesson_key=key)
                    logger.info(
                        "Обновлено событие: %s - Update: %s",
                        ev.get("summary"),
                        update_time,
                    )
        except Exception as e:
            logger.error("Ошибка при обновлении/воссоздании события: %s", e)

    # 8) persist
    try:
        save_lessons_to_db(schedule)
        logger.info("Текущее расписание сохранено в базу данных.")
    except Exception as e:
        logger.error("Ошибка при сохранении расписания: %s", e)
