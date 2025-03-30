import logging
from datetime import datetime
import pytz


def generate_lesson_key(lesson: dict) -> str:
    return f"{lesson['date']}_{lesson['time_range']}_{lesson['discipline']}_{lesson['teacher']}"


def create_event(lesson: dict, is_first_of_day: bool = False) -> dict:
    # Извлекаем дату: если есть день недели, берем второй элемент
    date_parts = lesson["date"].split(" ")
    date_str = date_parts[1] if len(date_parts) > 1 else date_parts[0]
    date = datetime.strptime(date_str, "%d.%m.%Y").date()

    # Разбиваем диапазон времени, например "18:30-20:00"
    start_time_str, end_time_str = lesson["time_range"].split("-")
    start_time = datetime.strptime(start_time_str.strip(), "%H:%M").time()
    end_time = datetime.strptime(end_time_str.strip(), "%H:%M").time()

    timezone = pytz.timezone("Asia/Vladivostok")
    start_datetime = timezone.localize(datetime.combine(date, start_time))
    end_datetime = timezone.localize(datetime.combine(date, end_time))

    update_time = datetime.now(timezone).strftime("%m.%d в %H:%M")

    reminders = {
        "useDefault": False,
        "overrides": []
    }
    if is_first_of_day:
        reminders["overrides"].append({"method": "popup", "minutes": 60})
        reminders["overrides"].append({"method": "popup", "minutes": 10})
    else:
        reminders["overrides"].append({"method": "popup", "minutes": 10})

    event = {
        "summary": f"{lesson['discipline']} ({lesson['lesson_type']})",
        "location": lesson["auditorium"],
        "description": f"Преподаватель: {lesson['teacher']}\nUpdate: {update_time}",
        "start": {
            "dateTime": start_datetime.isoformat(),
            "timeZone": "Asia/Vladivostok",
        },
        "end": {
            "dateTime": end_datetime.isoformat(),
            "timeZone": "Asia/Vladivostok",
        },
        "extendedProperties": {
            "private": {
                "lesson_key": generate_lesson_key(lesson)
            }
        },
        "reminders": reminders
    }
    return event
