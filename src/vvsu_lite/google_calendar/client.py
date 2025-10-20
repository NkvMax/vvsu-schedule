import os
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def _sa_path() -> str:
    path = os.getenv("GOOGLE_SA_JSON") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not path:
        raise RuntimeError("Нужно указать GOOGLE_SA_JSON или GOOGLE_APPLICATION_CREDENTIALS")
    return path

def load_service(logger):
    creds = service_account.Credentials.from_service_account_file(_sa_path(), scopes=SCOPES)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def _list_all_calendars(service):
    token = None
    while True:
        resp = service.calendarList().list(pageToken=token, maxResults=250).execute()
        for it in resp.get("items", []):
            yield it
        token = resp.get("nextPageToken")
        if not token:
            break

def find_calendar_id(service, logger, summary: Optional[str]=None, calendar_id: Optional[str]=None) -> str:
    if calendar_id:
        return calendar_id
    if not summary:
        summary = os.getenv("GCAL_CALENDAR_SUMMARY", "").strip()
    if not summary:
        if os.getenv("GCAL_CREATE_IF_MISSING") == "1":
            summary = os.getenv("GCAL_DEFAULT_SUMMARY", "VVSU Lite")
            logger.warning("GCAL_CALENDAR_SUMMARY не задан -> используем по умолчанию: %s", summary)
        else:
            raise RuntimeError("Нужно задать GCAL_CALENDAR_SUMMARY или GCAL_CALENDAR_ID")

    for it in _list_all_calendars(service):
        if it.get("summary") == summary:
            return it["id"]

    if os.getenv("GCAL_CREATE_IF_MISSING") == "1":
        tz = os.getenv("GCAL_NEW_CALENDAR_TZ", os.getenv("TIMEZONE", "UTC"))
        body = {"summary": summary, "timeZone": tz}
        cal = service.calendars().insert(body=body).execute()
        logger.info("Создан календарь '%s' (%s)", summary, cal["id"])
        return cal["id"]

    raise RuntimeError(f"Календарь с именем '{summary}' не найден. Задайте GCAL_CALENDAR_ID или включите GCAL_CREATE_IF_MISSING=1.")

def share_calendar_if_needed(service, calendar_id: str, logger):
    gmail = os.getenv("GCAL_SHARE_GMAIL", "").strip()
    if not gmail:
        return
    role = os.getenv("GCAL_SHARE_ROLE", "writer")
    try:
        acl = service.acl().list(calendarId=calendar_id, maxResults=250).execute()
        for rule in acl.get("items", []):
            scope = rule.get("scope") or {}
            if scope.get("type") == "user" and scope.get("value") == gmail:
                logger.info("Календарь уже расшарен на %s (role=%s)", gmail, rule.get("role"))
                return
        body = {"role": role, "scope": {"type": "user", "value": gmail}}
        service.acl().insert(calendarId=calendar_id, body=body).execute()
        logger.info("Выдал доступ %s=%s к календарю %s", gmail, role, calendar_id)
    except HttpError as e:
        logger.warning("Не удалось расшарить календарь на %s: %s", gmail, e)
