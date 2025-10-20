import os, hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def _svc():
    creds_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds)

def _key(d: dict) -> str:
    src = f"{d.get('date')}|{d.get('time_range')}|{d.get('discipline')}|{d.get('lesson_type')}|{d.get('auditorium')}|{d.get('teacher')}"
    return hashlib.sha1(src.encode('utf-8')).hexdigest()[:16]

def resolve_calendar_id(service, calendar_id: str | None, calendar_name: str | None) -> str:
    if calendar_id:
        return calendar_id
    if not calendar_name:
        raise RuntimeError("Provide CALENDAR_ID or CALENDAR_NAME")
    page_token = None
    while True:
        resp = service.calendarList().list(pageToken=page_token).execute()
        for cal in resp.get("items", []):
            if cal.get("summary") == calendar_name:
                return cal["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    raise RuntimeError(f"Calendar with name '{calendar_name}' not found")

def upsert_events(lessons, timezone: str, calendar_id: str | None = None, calendar_name: str | None = None, logger=None):
    svc = _svc()
    cid = resolve_calendar_id(svc, calendar_id, calendar_name)
    tz = ZoneInfo(timezone)

    for l in lessons:
        d = l.__dict__ if hasattr(l, '__dict__') else l
        key = _key(d)
        day = l.get_date()
        start_t, end_t = l.get_start_end_times()
        start = datetime.combine(day, start_t).replace(tzinfo=tz).isoformat()
        end   = datetime.combine(day, end_t).replace(tzinfo=tz).isoformat()

        body = {
            "summary": f"{l.discipline} ({l.lesson_type})",
            "location": l.auditorium,
            "description": f"Преподаватель: {l.teacher}",
            "start": {"dateTime": start},
            "end":   {"dateTime": end},
            "extendedProperties": {"private": {"lessonKey": key}},
        }

        found = svc.events().list(calendarId=cid, privateExtendedProperty=f"lessonKey={key}", timeMin=start, timeMax=end, singleEvents=True).execute().get("items", [])
        if found:
            eid = found[0]["id"]
            svc.events().update(calendarId=cid, eventId=eid, body=body).execute()
            if logger: logger.info(f"Updated: {body['summary']} {start} -> {end}")
        else:
            svc.events().insert(calendarId=cid, body=body).execute()
            if logger: logger.info(f"Inserted: {body['summary']} {start} -> {end}")
