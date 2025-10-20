
import os
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

# Event ID rules
ID_ALLOWED = re.compile(r'^[a-z0-9]{5,1024}$')
ID_PREFIX = "vvsu"

def _tz() -> str:
    return os.getenv("TIMEZONE", "Asia/Vladivostok")

def _horizon_days() -> int:
    try:
        return int(os.getenv("HORIZON_DAYS", "180"))
    except Exception:
        return 180

def _reminder_minutes() -> int:
    try:
        return int(os.getenv("REMINDER_MINUTES", "10"))
    except Exception:
        return 10

def _remove_missing() -> bool:
    return os.getenv("GCAL_REMOVE_MISSING", "0") == "1"

def _rfc3339(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")

def _parse_dt(date_str: str, time_str: str, tz: str) -> datetime:
    d = datetime.strptime(date_str, "%d.%m.%Y")
    t = datetime.strptime(time_str, "%H:%M").time()
    return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=ZoneInfo(tz))

def _split_time_range(time_range: str) -> Tuple[str, str]:
    parts = time_range.replace(' ', '').split('-')
    if len(parts) != 2:
        raise ValueError(f"Bad time_range: {time_range!r}")
    return parts[0], parts[1]

def _fingerprint(lesson) -> str:
    pieces = [
        lesson.date,
        lesson.time_range,
        lesson.discipline,
        getattr(lesson, "teacher", "") or "",
        getattr(lesson, "auditorium", "") or "",
        getattr(lesson, "lesson_type", "") or "",
        getattr(lesson, "webinar_url", "") or "",
    ]
    return hashlib.sha1("|".join(pieces).encode("utf-8")).hexdigest()

def make_event_id(lesson) -> str:
    h = _fingerprint(lesson)
    eid = f"{ID_PREFIX}{h}".lower()
    # Safety: ограничим алфавит и длину
    if not ID_ALLOWED.match(eid):
        eid = re.sub(r'[^a-z0-9]', '', eid) or f"{ID_PREFIX}{h}"
    return eid[:1024]

def _build_description(lesson) -> str:
    lines = []
    teacher = getattr(lesson, "teacher", None)
    if teacher:
        lines.append(f"Преподаватель: {teacher}")
    lesson_type = getattr(lesson, "lesson_type", None)
    if lesson_type:
        lines.append(f"Форма: {lesson_type}")
    auditorium = getattr(lesson, "auditorium", None)
    if auditorium:
        lines.append(f"Аудитория: {auditorium}")
    webinar = getattr(lesson, "webinar_url", None)
    if webinar:
        lines.append(f"Вебинар: {webinar}")
    return "\n".join(lines)

def _event_body(lesson) -> Dict:
    tz = _tz()
    start_s, end_s = _split_time_range(lesson.time_range)
    dt_start = _parse_dt(lesson.date, start_s, tz)
    dt_end   = _parse_dt(lesson.date, end_s, tz)

    minutes = _reminder_minutes()
    reminders = {"useDefault": True}
    if minutes and minutes > 0:
        reminders = {"useDefault": False, "overrides": [{"method": "popup", "minutes": minutes}]}

    body = {
        "summary": lesson.discipline,
        "description": _build_description(lesson),
        "start": {"dateTime": _rfc3339(dt_start), "timeZone": tz},
        "end":   {"dateTime": _rfc3339(dt_end),   "timeZone": tz},
        "reminders": reminders,
        "extendedProperties": {
            "private": {
                "vvsu.fingerprint": _fingerprint(lesson),
                "vvsu.webinar_url": (getattr(lesson, "webinar_url", "") or ""),
            }
        }
    }

    # Предпочитаем ссылку на вебинар как location, иначе аудиторию
    if getattr(lesson, "webinar_url", None):
        body["location"] = lesson.webinar_url
    elif getattr(lesson, "auditorium", None):
        body["location"] = lesson.auditorium

    return body

def _equal_event(existing: Dict, desired: Dict) -> bool:
    for k in ("summary", "description", "location"):
        if (existing.get(k) or "") != (desired.get(k) or ""):
            return False

    for edge in ("start", "end"):
        a, b = existing.get(edge, {}), desired.get(edge, {})
        if (a.get("dateTime") or "") != (b.get("dateTime") or ""):
            return False
        if (a.get("timeZone") or "") != (b.get("timeZone") or ""):
            return False

    a, b = existing.get("reminders", {}), desired.get("reminders", {})
    if (a.get("useDefault") != b.get("useDefault")):
        return False
    if not a.get("useDefault"):
        if (a.get("overrides") or []) != (b.get("overrides") or []):
            return False

    ap = ((existing.get("extendedProperties") or {}).get("private") or {})
    bp = ((desired.get("extendedProperties") or {}).get("private") or {})
    for k in ("vvsu.fingerprint", "vvsu.webinar_url"):
        if (ap.get(k) or "") != (bp.get(k) or ""):
            return False

    return True

def _list_existing_events(service, calendar_id: str, time_min: str, time_max: str) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    token = None
    while True:
        resp = service.events().list(
            calendarId=calendar_id,
            singleEvents=True,
            showDeleted=False,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=2500,
            pageToken=token,
        ).execute()
        for ev in resp.get("items", []):
            if "id" in ev:
                out[ev["id"]] = ev
        token = resp.get("nextPageToken")
        if not token:
            break
    return out

def _window_now_to_horizon(tz: str) -> Tuple[str, str]:
    now = datetime.now(ZoneInfo(tz))
    hi  = now + timedelta(days=_horizon_days())
    return now.isoformat(timespec="seconds"), hi.isoformat(timespec="seconds")

def upsert_to_calendar(service, calendar_id: str, lessons: List, logger):
    tz = _tz()
    time_min, time_max = _window_now_to_horizon(tz)

    existing = _list_existing_events(service, calendar_id, time_min, time_max)

    desired_map: Dict[str, Dict] = {}
    order: List[str] = []

    for lesson in lessons:
        eid = make_event_id(lesson)
        body = _event_body(lesson)
        body_with_id = {**body, "id": eid}
        desired_map[eid] = body_with_id
        order.append(eid)

    created = updated = unchanged = 0
    for eid in order:
        body = desired_map[eid]
        cur = existing.get(eid)
        if not cur:
            logger.debug("insert event id=%s", eid)
            service.events().insert(calendarId=calendar_id, body=body, sendUpdates="none").execute()
            created += 1
        else:
            if _equal_event(cur, body):
                unchanged += 1
            else:
                logger.debug("update event id=%s", eid)
                service.events().update(calendarId=calendar_id, eventId=eid, body=body, sendUpdates="none").execute()
                updated += 1

    removed = 0
    if _remove_missing():
        keep = set(desired_map.keys())
        for eid, ev in list(existing.items()):
            if not eid.startswith(ID_PREFIX):
                continue
            if eid not in keep:
                logger.debug("delete event id=%s", eid)
                service.events().delete(calendarId=calendar_id, eventId=eid, sendUpdates="none").execute()
                removed += 1

    logger.info(
        "Google Calendar sync: created=%d, updated=%d, unchanged=%d%s",
        created, updated, unchanged,
        f", removed={removed}" if _remove_missing() else ""
    )
