from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Tuple


# утилиты времени (ISO с таймзоной +HH:MM)
def parse_iso(s: str) -> datetime:
    # Поддержка 'Z' и '+HH:MM'
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def to_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)


# ключ события
def make_uid(summary: str, start_iso: str, location: str | None = None) -> str:
    base = f"{summary}|{start_iso}|{location or ''}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:32]


# нормализация полезной нагрузки для сравнения
SIGNIFICANT_FIELDS = ("summary", "description", "location", "start", "end")


def normalize_event_payload(e: Dict[str, Any]) -> Dict[str, Any]:
    # Берем только существенное + extendedProperties.private.vvsu_uid
    norm = {k: e.get(k) for k in SIGNIFICANT_FIELDS}
    uid = e.get("extendedProperties", {}).get("private", {}).get("vvsu_uid")
    if uid:
        norm["vvsu_uid"] = uid
    return norm


# чтение существующих событий в Google
def list_existing_map(
    service, calendar_id: str, time_min: str, time_max: str
) -> Dict[str, Dict[str, Any]]:
    """
    Возвращает {uid: google_event}, где uid = extendedProperties.private.vvsu_uid
    (если нет — падаем обратно на summary+startTime).
    """
    existing: Dict[str, Dict[str, Any]] = {}
    page = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page,
            )
            .execute()
        )
        for ev in resp.get("items", []):
            uid = ev.get("extendedProperties", {}).get("private", {}).get("vvsu_uid")
            if not uid:
                start = ev["start"].get("dateTime") or ev["start"].get("date")
                uid = make_uid(ev.get("summary", ""), start or "", ev.get("location"))
            existing[uid] = ev
        page = resp.get("nextPageToken")
        if not page:
            break
    return existing


# upsert всех занятий
def reconcile_lessons(
    service,
    calendar_id: str,
    lessons: Iterable[Dict[str, Any]],
    *,
    prune_extra: bool = False,
) -> Tuple[int, int, int]:
    """
    lessons — iterable из уже построенных payload'ов Google Events
    (dict с 'summary', 'start', 'end', опц. 'location'/'description').

    Возвращает (inserted, updated, deleted)
    """
    # вычислим временной интервал из уроков
    starts = []
    ends = []
    lesson_payloads = []
    for ev in lessons:
        start = ev["start"].get("dateTime") or ev["start"].get("date")
        end = ev["end"].get("dateTime") or ev["end"].get("date")
        starts.append(parse_iso(start))
        ends.append(parse_iso(end))
        lesson_payloads.append(ev)

    if not lesson_payloads:
        return (0, 0, 0)

    tmin = to_utc(min(starts)).isoformat().replace("+00:00", "Z")
    tmax = to_utc(max(ends)).isoformat().replace("+00:00", "Z")

    existing = list_existing_map(service, calendar_id, tmin, tmax)

    inserted = updated = 0
    desired_uids = set()

    for body in lesson_payloads:
        start_iso = body["start"].get("dateTime") or body["start"].get("date")
        uid = (
            body.get("extendedProperties", {}).get("private", {}).get("vvsu_uid")
        ) or make_uid(body.get("summary", ""), start_iso, body.get("location"))

        # гарантируем, что uid уходит в extendedProperties
        ep = body.setdefault("extendedProperties", {}).setdefault("private", {})
        ep["vvsu_uid"] = uid
        desired_uids.add(uid)

        ex = existing.get(uid)
        if not ex:
            # вставка
            service.events().insert(calendarId=calendar_id, body=body).execute()
            inserted += 1
        else:
            # сравнить “существенное”, при различиях — update
            if normalize_event_payload(body) != normalize_event_payload(ex):
                service.events().update(
                    calendarId=calendar_id, eventId=ex["id"], body=body
                ).execute()
                updated += 1

    deleted = 0
    if prune_extra:
        # удалим события, которых уже нет в БД
        for uid, ex in existing.items():
            if uid not in desired_uids:
                service.events().delete(
                    calendarId=calendar_id, eventId=ex["id"]
                ).execute()
                deleted += 1

    return (inserted, updated, deleted)
