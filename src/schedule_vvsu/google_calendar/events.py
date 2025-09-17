from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

import pytz

try:
    # project structure
    from schedule_vvsu.config import get_settings
except Exception:
    # standalone fallback (tests)
    class _S:
        TIMEZONE = "Asia/Vladivostok"

    def get_settings():
        return _S()


_URL_RE = re.compile(r"(https?://\S+|\b[\w.-]+\.[a-z]{2,}/\S+)", re.I)
_TAIL_RE = re.compile(
    r"\s*вебинар\s*:?\s*(https?://\S+|[\w.-]+\.[a-z]{2,}/\S+)\s*", re.I
)

settings = get_settings()


def extract_webinar_url(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = _URL_RE.search(text)
    if not m:
        return None
    url = m.group(1)
    if not url.lower().startswith("http"):
        url = "https://" + url
    return url


def clean_title(text: Optional[str]) -> str:
    if not text:
        return ""
    return _TAIL_RE.sub("", text).strip()


def generate_lesson_key(lesson: Dict[str, Any]) -> str:
    """
    Stable key by (date, start_time/time_range start, cleaned title, lesson_type).
    Accepts lesson as dict (from DTO .dict()).
    """
    date = lesson.get("date", "")
    start = (lesson.get("time_range") or "").split("-")[0].strip() or lesson.get(
        "start_time", ""
    )
    if isinstance(start, str):
        start = start[:5]  # "18:30:00" -> "18:30"
    title = clean_title(lesson.get("discipline") or lesson.get("subject") or "")
    typ = (lesson.get("lesson_type") or "").strip().lower()
    return f"{date}|{start}|{title}|{typ}".lower()


def build_description(lesson: Dict[str, Any], update_time: str) -> str:
    parts = []
    teacher = lesson.get("teacher")
    if teacher:
        parts.append(f"Преподаватель: {teacher}")
    url = extract_webinar_url(lesson.get("discipline") or lesson.get("subject") or "")
    if url:
        parts.append(f"Ссылка: {url}")
    parts.append(f"Update: {update_time}")
    return "\n".join(parts)


def _parse_dt_local(date_str: str, hhmm: str) -> str:
    tz = pytz.timezone(settings.TIMEZONE)
    dt = datetime.strptime(f"{date_str} {hhmm}", "%d.%m.%Y %H:%M")
    return tz.localize(dt).isoformat()


def _reminders_payload(is_first_of_day: bool) -> Dict[str, Any]:
    """Формирует блок reminders для события."""
    if is_first_of_day:
        overrides = [
            {"method": "popup", "minutes": 60},
            {"method": "popup", "minutes": 10},
        ]
    else:
        overrides = [{"method": "popup", "minutes": 10}]
    return {"useDefault": False, "overrides": overrides}


def create_event(
    lesson: Dict[str, Any],
    is_first_of_day: bool = False,
    lesson_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build event body for Calendar API insert().
    - Для первой пары дня: напоминания за 60 и за 10 минут.
    - Для остальных пар: напоминание за 10 минут.
    """
    date = lesson["date"]
    start_s, end_s = (lesson.get("time_range") or "").split("-")
    start_iso = _parse_dt_local(date, start_s.strip())
    end_iso = _parse_dt_local(date, end_s.strip())

    title = clean_title(lesson.get("discipline") or lesson.get("subject") or "")
    summary = f"{title} ({lesson['lesson_type']})"

    url = extract_webinar_url(lesson.get("discipline") or lesson.get("subject") or "")
    room = (lesson.get("auditorium") or lesson.get("room") or "").strip()
    # если аудитория — вебинарная платформа и есть URL — кладем URL в location
    location = (
        url if (room and "вебинарная платформа" in room.lower() and url) else room
    )

    tz = pytz.timezone(settings.TIMEZONE)
    update_time = datetime.now(tz).strftime("%m.%d в %H:%M")

    body = {
        "summary": summary,
        "start": {"dateTime": start_iso, "timeZone": settings.TIMEZONE},
        "end": {"dateTime": end_iso, "timeZone": settings.TIMEZONE},
        "location": location,
        "description": build_description(lesson, update_time),
        # lesson_key нужен для идемпотентности
        "extendedProperties": {
            "private": {"lesson_key": lesson_key or generate_lesson_key(lesson)}
        },
        # скрыть "кто создал" увы нельзя через API — это системное поле Google
        "guestsCanInviteOthers": False,
        "guestsCanSeeOtherGuests": False,
        "reminders": _reminders_payload(is_first_of_day),
    }
    return body


def update_event(
    service,
    calendar_id: str,
    event: Dict[str, Any],
    lesson_obj,
    lesson_key: Optional[str] = None,
):
    """
    Update existing event: summary, description (с ссылкой), location, extendedProperties.
    lesson_obj — это DTO Lesson (имеет .discipline, .lesson_type, .auditorium, .teacher, .dict()).
    """
    # summary без "вебинар: ..."
    title = clean_title(
        getattr(lesson_obj, "discipline", None) or getattr(lesson_obj, "subject", None)
    )
    event["summary"] = f"{title} ({getattr(lesson_obj, 'lesson_type', '')})".strip()

    # location
    disc = getattr(lesson_obj, "discipline", None) or getattr(
        lesson_obj, "subject", None
    )
    url = extract_webinar_url(disc)
    room = (
        getattr(lesson_obj, "auditorium", None)
        or getattr(lesson_obj, "room", None)
        or ""
    ).strip()
    event["location"] = (
        url if (room and "вебинарная платформа" in room.lower() and url) else room
    )

    # description — всегда через build_description, чтобы ссылка была
    tz = pytz.timezone(settings.TIMEZONE)
    update_time = datetime.now(tz).strftime("%m.%d в %H:%M")
    event["description"] = build_description(
        getattr(lesson_obj, "dict", lambda: {})(), update_time
    )

    if lesson_key:
        event.setdefault("extendedProperties", {}).setdefault("private", {})[
            "lesson_key"
        ] = lesson_key

    return (
        service.events()
        .update(calendarId=calendar_id, eventId=event["id"], body=event)
        .execute()
    )
