import logging
from datetime import datetime
import pytz
from collections import defaultdict

from schedule_vvsu.dto.models import Lesson
from schedule_vvsu.database import load_lessons_from_db, save_lessons_to_db, SessionLocal
from schedule_vvsu.db.models import ExcludedLesson
from schedule_vvsu.google_calendar.events import create_event, generate_lesson_key
from schedule_vvsu.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def filter_excluded_lessons(schedule: list[Lesson]) -> list[Lesson]:
    """
    Исключает занятия, подходящие под критерии ExcludedLesson из БД.
    """
    session = SessionLocal()
    try:
        excluded = session.query(ExcludedLesson).all()
        result = []
        for lesson in schedule:
            should_exclude = any(
                ex.title == lesson.discipline and
                (ex.teacher is None or ex.teacher == lesson.teacher) and
                (ex.weekday is None or ex.weekday == lesson.weekday) and
                (ex.start_time is None or ex.start_time == lesson.start_time)
                for ex in excluded
            )
            if not should_exclude:
                result.append(lesson)
        return result
    finally:
        session.close()


def get_existing_event(service, calendar_id, lesson_key):
    """Проверяет наличие события с уникальным ключом."""
    events = service.events().list(
        calendarId=calendar_id,
        privateExtendedProperty=f"lesson_key={lesson_key}",
        singleEvents=True
    ).execute().get("items", [])
    return events[0] if events else None


def update_event(service, calendar_id, event, lesson):
    """Обновляет существующее событие."""
    event['summary'] = f"{lesson['discipline']} ({lesson['lesson_type']})"
    event['location'] = lesson['auditorium']
    event['description'] = f"Преподаватель: {lesson['teacher']}\nUpdate: {datetime.now().strftime('%m.%d в %H:%M')}"
    service.events().update(calendarId=calendar_id, eventId=event['id'], body=event).execute()


def is_past_event(lesson: Lesson) -> bool:
    try:
        start_time = lesson.get_start_end_times()[0]
        lesson_datetime = datetime.strptime(f"{lesson.date} {start_time}", "%d.%m.%Y %H:%M")
        lesson_datetime = pytz.timezone(settings.TIMEZONE).localize(lesson_datetime)
        return lesson_datetime < datetime.now(pytz.timezone(settings.TIMEZONE))
    except Exception as e:
        logger.warning(f"Ошибка при проверке прошедшего события: {e}")
        return False


def sync_schedule_to_calendar(service, schedule: list[Lesson], calendar_id: str):
    """
    Синхронизирует занятия между расписанием и Google Calendar.
    """
    try:
        previous_schedule = load_lessons_from_db()
        logger.info("Загружено предыдущее расписание из БД.")
    except Exception as e:
        previous_schedule = []
        logger.warning(f"Ошибка загрузки предыдущего расписания: {e}")

    schedule = filter_excluded_lessons(schedule)

    # Генерация ключей
    lesson_key = lambda lesson: generate_lesson_key(lesson.dict())
    prev_keys = {lesson_key(lesson) for lesson in previous_schedule}
    curr_keys = {lesson_key(lesson) for lesson in schedule}

    added = [lesson for lesson in schedule if lesson_key(lesson) not in prev_keys]
    removed = [lesson for lesson in previous_schedule if lesson_key(lesson) not in curr_keys]
    common_keys = prev_keys & curr_keys

    logger.info(f"Добавлено занятий: {len(added)}")
    logger.info(f"Удалено занятий: {len(removed)}")

    # Сортировка и группировка для определения первых занятий
    sorted_schedule = sorted(schedule, key=lambda l: (l.get_date(), l.get_start_end_times()[0]))
    grouped = defaultdict(list)
    for lesson in sorted_schedule:
        grouped[lesson.get_date()].append(lesson)
    first_lessons = {day: lessons[0] for day, lessons in grouped.items()}

    # Добавление и обновление событий
    for lesson in added:
        is_first = lesson == first_lessons.get(lesson.get_date())
        key = lesson_key(lesson)
        event_body = create_event(lesson.dict(), is_first_of_day=is_first)

        try:
            existing = get_existing_event(service, calendar_id, key)
            if existing:
                logger.info(f"Обновление события для {lesson.discipline}")
                update_event(service, calendar_id, existing, lesson)
            else:
                event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
                logger.info(f"Добавлено событие: {event.get('summary')} ({event.get('start')['dateTime']})")
        except Exception as e:
            logger.error(f"Ошибка при добавлении/обновлении события: {e}")

    # Удаление только будущих событий
    for lesson in removed:
        if is_past_event(lesson):
            logger.info(f"Пропущено удаление прошедшего события: {lesson.discipline} {lesson.date}")
            continue

        key = lesson_key(lesson)
        try:
            events = service.events().list(
                calendarId=calendar_id,
                privateExtendedProperty=f"lesson_key={key}",
                singleEvents=True
            ).execute().get("items", [])
            for ev in events:
                service.events().delete(calendarId=calendar_id, eventId=ev["id"]).execute()
                logger.info(f"Удалено событие: {ev.get('summary')}")
        except Exception as e:
            logger.error(f"Ошибка при удалении события: {e}")

    # Обновление описаний общих событий
    tz = pytz.timezone(settings.TIMEZONE)
    update_time = datetime.now(tz).strftime("%m.%d в %H:%M")
    for lesson in schedule:
        key = lesson_key(lesson)
        if key in common_keys:
            try:
                events = service.events().list(
                    calendarId=calendar_id,
                    privateExtendedProperty=f"lesson_key={key}",
                    singleEvents=True
                ).execute().get("items", [])
                for ev in events:
                    ev["description"] = f"Преподаватель: {lesson.teacher}\nUpdate: {update_time}"
                    updated = service.events().update(calendarId=calendar_id, eventId=ev["id"], body=ev).execute()
                    logger.info(f"Обновлено событие: {updated.get('summary')} - Update: {update_time}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении описания события: {e}")

    # Сохраняем текущее расписание
    try:
        save_lessons_to_db(schedule)
        logger.info("Текущее расписание сохранено в базу данных.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении расписания: {e}")
