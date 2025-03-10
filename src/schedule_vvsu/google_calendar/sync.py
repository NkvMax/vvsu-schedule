# src/google_calendar/sync.py
import logging
import json
from datetime import datetime
import pytz
from pathlib import Path
from collections import defaultdict

from schedule_vvsu.dto.models import Lesson
from .events import create_event, generate_lesson_key


def sync_schedule_to_calendar(service, schedule: list[Lesson], calendar_id: str):
    """
    Синхронизирует расписание (список Lesson) с Google Calendar:
      - Добавляет новые события
      - Удаляет исчезнувшие
      - Обновляет оставшиеся
    """
    base_dir = Path(__file__).resolve().parent.parent
    prev_sched_path = base_dir / "json" / "previous_schedule.json"

    # Загружаем прошлое расписание
    if prev_sched_path.exists():
        with prev_sched_path.open("r", encoding="utf-8") as f:
            data = json.load(f)  # список словарей
        logging.info("Загружено предыдущее расписание из previous_schedule.json.")
        # Превращаем словари в объекты Lesson
        previous_schedule = [Lesson(**item) for item in data]
    else:
        previous_schedule = []
        logging.info("Файл previous_schedule.json не найден. Начинаем с пустого расписания.")

    # Генерация ключей
    def lesson_key(lesson: Lesson) -> str:
        # Или можно вызывать generate_lesson_key(lesson.dict())
        return generate_lesson_key(lesson.dict())

    previous_keys = {lesson_key(lesson) for lesson in previous_schedule}
    current_keys = {lesson_key(lesson) for lesson in schedule}

    added_lessons = [lesson for lesson in schedule if lesson_key(lesson) not in previous_keys]
    removed_lessons = [lesson for lesson in previous_schedule if lesson_key(lesson) not in current_keys]

    logging.info(f"Добавлено занятий: {len(added_lessons)}")
    logging.info(f"Удалено занятий: {len(removed_lessons)}")

    # Сортируем
    def lesson_sort_key(lesson: Lesson):
        # Используем методы DTO
        dt = lesson.get_date()
        start_time, _ = lesson.get_start_end_times()
        return dt, start_time

    schedule_sorted = sorted(schedule, key=lesson_sort_key)
    grouped = defaultdict(list)
    for lesson in schedule_sorted:
        grouped[lesson.get_date()].append(lesson)

    # Определяем первую пару дня
    first_lessons = {date_obj: lessons[0] for date_obj, lessons in grouped.items()}

    # Добавление новых событий
    for lesson in added_lessons:
        date_obj = lesson.get_date()
        is_first_of_day = (lesson == first_lessons.get(date_obj))
        event_body = create_event(lesson.dict(), is_first_of_day=is_first_of_day)

        try:
            created_event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
            logging.info(f"Добавлено событие: {created_event.get('summary')} "
                         f"({created_event.get('start')['dateTime']})")
        except Exception as e:
            logging.error(f"Ошибка при добавлении события: {e}")

    # Удаление устаревших
    for lesson in removed_lessons:
        key = lesson_key(lesson)
        try:
            events_list = service.events().list(
                calendarId=calendar_id,
                privateExtendedProperty=f"lesson_key={key}",
                singleEvents=True
            ).execute().get("items", [])
            for ev in events_list:
                service.events().delete(calendarId=calendar_id, eventId=ev["id"]).execute()
                logging.info(f"Удалено событие: {ev.get('summary')}")
        except Exception as e:
            logging.error(f"Ошибка при удалении события: {e}")

    # Обновление оставшихся
    common_keys = previous_keys.intersection(current_keys)
    timezone = pytz.timezone("Asia/Vladivostok")
    for lesson in schedule:
        key = lesson_key(lesson)
        if key in common_keys:
            update_time = datetime.now(timezone).strftime("%m.%d в %H:%M")
            new_description = f"Преподаватель: {lesson.teacher}\nUpdate: {update_time}"
            try:
                events_list = service.events().list(
                    calendarId=calendar_id,
                    privateExtendedProperty=f"lesson_key={key}",
                    singleEvents=True
                ).execute().get("items", [])
                for ev in events_list:
                    ev["description"] = new_description
                    updated_event = service.events().update(calendarId=calendar_id, eventId=ev["id"], body=ev).execute()
                    logging.info(f"Обновлено событие: {updated_event.get('summary')} - Update: {update_time}")
            except Exception as e:
                logging.error(f"Ошибка при обновлении события: {e}")

    # Сохраняем текущее расписание в виде словарей
    try:
        with prev_sched_path.open("w", encoding="utf-8") as f:
            # Сериализуем пары (Lesson) обратно в словари
            json.dump([l.dict() for l in schedule], f, indent=4, ensure_ascii=False)
        logging.info(f"Текущее расписание сохранено в {prev_sched_path}.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении расписания: {e}")
