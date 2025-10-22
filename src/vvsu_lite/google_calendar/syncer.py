from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from zoneinfo import ZoneInfo
import os

from googleapiclient.errors import HttpError

# Settings & constants

DEFAULT_TZ = os.getenv("LOCAL_TZ", os.getenv("TIMEZONE", "Asia/Vladivostok"))
HORIZON_DAYS = int(os.getenv("HORIZON_DAYS", "180"))
ID_PREFIX = os.getenv("GCAL_ID_PREFIX", "vvsu")

def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(DEFAULT_TZ)
    except Exception:
        return ZoneInfo("UTC")

def _window_now_to_horizon(tz: ZoneInfo) -> Tuple[str, str]:
    now = datetime.now(tz)
    return now.isoformat(), (now + timedelta(days=HORIZON_DAYS)).isoformat()

def _remove_missing() -> bool:
    return os.getenv("GCAL_REMOVE_MISSING", "0") == "1"

# Helpers

_TAIL_RE = re.compile(r"( вебинар:.*)$", re.IGNORECASE)

def clean_title(text: Optional[str]) -> str:
    if not text:
        return ""
    return _TAIL_RE.sub("", text).strip()

_URL_RE = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)

def extract_webinar_url_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    m = _URL_RE.search(text)
    if not m:
        # иногда формат "вебинар: <URL>"
        parts = text.split("вебинар:")
        if len(parts) > 1:
            guess = parts[1].strip().split()[0]
            if guess and not guess.lower().startswith("http"):
                guess = "https://" + guess
            return guess
        return None
    url = m.group(1).strip()
    if url and not url.lower().startswith("http"):
        url = "https://" + url
    return url

def resolve_webinar_url(d: Dict[str, Any]) -> Optional[str]:
    """Prefer explicit field; fallback to parsing discipline/subject."""
    return d.get("webinar_url") or extract_webinar_url_from_text(
        d.get("discipline") or d.get("subject") or ""
    )

def generate_lesson_key(lesson: Dict[str, Any]) -> str:
    """Stable key: (date | start | cleaned title | lesson_type) lower-case."""
    date = lesson.get("date", "")
    tr = (lesson.get("time_range") or "")
    start = tr.replace("—", "-").replace("–", "-").split("-")[0].strip()
    if isinstance(start, str):
        start = start[:5]  # "18:30:00" -> "18:30"
    title = clean_title(lesson.get("discipline") or lesson.get("subject") or "")
    typ = (lesson.get("lesson_type") or "").strip().lower()
    return f"{date}|{start}|{title}|{typ}".lower()

def make_event_id_from_key(key: str) -> str:
    return f"{ID_PREFIX}{hashlib.sha1(key.encode('utf-8')).hexdigest()}"

# Build event payload

def _parse_start_end(date_str: str, time_range: str, tz: ZoneInfo) -> Tuple[str, str]:
    s = time_range.replace("—", "-").replace("–", "-")
    parts = [p.strip() for p in s.split("-", 1)]
    if len(parts) != 2:
        raise ValueError(f"Bad time_range: {time_range!r}")
    fmt = "%H:%M:%S" if parts[0].count(":") == 2 else "%H:%M"
    start_dt = datetime.strptime(f"{date_str} {parts[0]}", f"%d.%m.%Y {fmt}")
    end_dt   = datetime.strptime(f"{date_str} {parts[1]}", f"%d.%m.%Y {fmt}")
    start_iso = datetime.combine(start_dt.date(), start_dt.time(), tzinfo=tz).isoformat()
    end_iso   = datetime.combine(end_dt.date(), end_dt.time(), tzinfo=tz).isoformat()
    return start_iso, end_iso

def build_description(lesson: Dict[str, Any], tz: ZoneInfo) -> str:
    """Teacher, form, link and Update timestamp (local)."""
    parts: List[str] = []
    teacher = lesson.get("teacher")
    if teacher:
        parts.append(f"Преподаватель: {teacher}")
    form = (lesson.get("lesson_type") or "").strip()
    if form:
        parts.append(f"Форма: {form}")
    url = resolve_webinar_url(lesson)
    if url:
        parts.append(f"Ссылка: {url}")
    now = datetime.now(tz)
    update_time = now.strftime("%m.%d в %H:%M")
    parts.append(f"Update: {update_time}")
    return "\n".join(parts)

def _event_body(lesson_obj) -> Dict[str, Any]:
    # Accept dataclass or mapping
    if is_dataclass(lesson_obj):
        d = asdict(lesson_obj)
    elif isinstance(lesson_obj, dict):
        d = dict(lesson_obj)
    else:
        d = getattr(lesson_obj, "__dict__", {})
    tz = _tz()
    start_iso, end_iso = _parse_start_end(d["date"], d["time_range"], tz)
    title = clean_title(d.get("discipline") or d.get("subject") or "")
    summary = f"{title} ({d.get('lesson_type','')})".strip()
    room = (d.get("auditorium") or d.get("room") or "").strip()
    url = resolve_webinar_url(d)

    # Location logic:
    if url:
        location = url
    elif room and "вебинар" in room.lower():
        location = room
    else:
        location = room

    desc = build_description(d, tz)

    body: Dict[str, Any] = {
        "summary": summary,
        "location": location,
        "description": desc,
        "start": {"dateTime": start_iso, "timeZone": str(tz)},
        "end":   {"dateTime": end_iso,   "timeZone": str(tz)},
        "extendedProperties": {"private": {}}
    }
    # lesson_key & updated_at
    key = generate_lesson_key(d)
    body["extendedProperties"]["private"]["lesson_key"] = key
    body["extendedProperties"]["private"]["updated_at"] = datetime.now(tz).isoformat()
    return body

# Equality ignoring 'Update:' line

def _norm_desc_no_update(text: str) -> str:
    if not text:
        return ""
    lines = [ln for ln in str(text).splitlines() if not ln.strip().startswith("Update:")]
    return "\n".join(lines).strip()

def _equal_event(cur: Dict[str, Any], desired: Dict[str, Any]) -> bool:
    if (cur.get("summary") or "") != (desired.get("summary") or ""):
        return False
    if (cur.get("location") or "") != (desired.get("location") or ""):
        return False
    def dt(ev, key): return ((ev.get(key) or {}).get("dateTime"))
    if dt(cur, "start") != dt(desired, "start"):
        return False
    if dt(cur, "end") != dt(desired, "end"):
        return False
    if _norm_desc_no_update(cur.get("description") or "") != _norm_desc_no_update(desired.get("description") or ""):
        return False
    return True

# Existing events fetch

def _fetch_events_map(service, calendar_id: str, time_min: str, time_max: str) -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
    by_id: Dict[str, Dict] = {}
    by_key: Dict[str, Dict] = {}
    token: Optional[str] = None
    while True:
        resp = service.events().list(
            calendarId=calendar_id,
            singleEvents=True,
            showDeleted=False,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=2500,
            pageToken=token
        ).execute()
        for ev in resp.get("items", []):
            eid = ev.get("id")
            if eid:
                by_id[eid] = ev
            key = ((ev.get("extendedProperties") or {}).get("private") or {}).get("lesson_key")
            if key:
                by_key[key] = ev
        token = resp.get("nextPageToken")
        if not token:
            break
    return by_id, by_key

# Main

def upsert_to_calendar(service, calendar_id: str, lessons: List, logger):
    tz = _tz()
    time_min, time_max = _window_now_to_horizon(tz)

    existing_by_id, existing_by_key = _fetch_events_map(service, calendar_id, time_min, time_max)

    created = updated = recreated = unchanged = 0
    desired_ids: List[str] = []

    # Build desired
    desired: Dict[str, Dict] = {}
    for lesson in lessons:
        body = _event_body(lesson)
        key = body["extendedProperties"]["private"]["lesson_key"]
        eid = make_event_id_from_key(key)
        body["id"] = eid
        desired[eid] = body
        desired_ids.append(eid)

    # Upsert
    for eid, body in desired.items():
        key = body["extendedProperties"]["private"]["lesson_key"]
        cur = existing_by_id.get(eid) or existing_by_key.get(key)

        if cur is None:
            logger.debug("insert event id=%s", eid)
            try:
                service.events().insert(calendarId=calendar_id, body=body, sendUpdates="none").execute()
            except HttpError as e:
                if getattr(getattr(e, "resp", None), "status", None) == 409:
                    service.events().update(calendarId=calendar_id, eventId=eid, body=body, sendUpdates="none").execute()
                else:
                    raise
            created += 1
            continue

        cur_id = cur.get("id")
        if cur_id != eid:
            logger.debug("recreate (normalize id) old_id=%s -> new_id=%s", cur_id, eid)
            try:
                service.events().delete(calendarId=calendar_id, eventId=cur_id, sendUpdates="none").execute()
            except Exception:
                pass
            try:
                service.events().insert(calendarId=calendar_id, body=body, sendUpdates="none").execute()
            except HttpError as e:
                if getattr(getattr(e, "resp", None), "status", None) == 409:
                    service.events().update(calendarId=calendar_id, eventId=eid, body=body, sendUpdates="none").execute()
                else:
                    raise
            recreated += 1
            continue

        if _equal_event(cur, body):
            unchanged += 1
        else:

            logger.debug("delete+create event id=%s (content changed)", eid)
            try:
                service.events().delete(calendarId=calendar_id, eventId=eid, sendUpdates="none").execute()
            except Exception:
                pass
            try:
                service.events().insert(calendarId=calendar_id, body=body, sendUpdates="none").execute()
            except HttpError as e:
                if getattr(getattr(e, "resp", None), "status", None) == 409:
                    service.events().update(calendarId=calendar_id, eventId=eid, body=body, sendUpdates="none").execute()
                else:
                    raise
            recreated += 1


    removed = 0
    if _remove_missing():
        keep = set(desired_ids)
        for eid, ev in list(existing_by_id.items()):
            if not str(eid).startswith(ID_PREFIX):
                continue
            if eid not in keep:
                try:
                    service.events().delete(calendarId=calendar_id, eventId=eid, sendUpdates="none").execute()
                    removed += 1
                except Exception:
                    pass

    logger.info(
        "Google Calendar sync: created=%d, recreated=%d, updated=%d, unchanged=%d%s",
        created, recreated, updated, unchanged,
        f", removed={removed}" if _remove_missing() else ""
    )
