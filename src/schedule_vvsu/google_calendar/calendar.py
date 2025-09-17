import logging
from typing import Optional

from sqlalchemy.orm import Session

from schedule_vvsu.config import get_settings
from schedule_vvsu.database import get_db
from schedule_vvsu.services.settings_service import get_user_mail_account

settings = get_settings()


def get_calendar_id(service, calendar_name: str) -> Optional[str]:
    """Пытается найти календарь по названию и вернуть его ID."""
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for cal in calendar_list.get("items", []):
            if cal.get("summary") == calendar_name:
                logging.info(
                    f"Найден календарь '{calendar_name}' с ID: {cal.get('id')}"
                )
                return cal.get("id")
        page_token = calendar_list.get("nextPageToken")
        if not page_token:
            break
    logging.info(f"Календарь '{calendar_name}' не найден.")
    return None


def create_calendar(service, calendar_name: str, db: Session = None) -> str:
    """Создает новый календарь и настраивает ACL-доступ."""
    body = {
        "summary": calendar_name,
        "timeZone": settings.TIMEZONE,
        "backgroundColor": "#668BE1",
        "foregroundColor": "#ffffff",
    }
    created_calendar = service.calendars().insert(body=body).execute()
    calendar_id = created_calendar.get("id")
    logging.info(f"Создан календарь: {calendar_id}")

    # Предоставление доступа пользователю
    try:
        acl_rule = {
            "scope": {
                "type": "user",
                "value": get_user_mail_account(db),  # Передаем db
            },
            "role": "owner",
        }
        created_rule = (
            service.acl().insert(calendarId=calendar_id, body=acl_rule).execute()
        )
        logging.info(f"ACL правило создано: {created_rule}")
    except Exception as e:
        logging.error(f"Ошибка при установке ACL для календаря: {e}")

    return calendar_id


def get_or_create_calendar(service, calendar_name: str, db: Session = None) -> str:
    """Получает ID календаря или создает новый, если не найден."""
    calendar_id = get_calendar_id(service, calendar_name)
    if calendar_id:
        logging.info(f"Используем существующий календарь '{calendar_name}'.")
        _ensure_user_access(service, calendar_id, db)
    else:
        logging.info(f"Создаем новый календарь '{calendar_name}'.")
        calendar_id = create_calendar(service, calendar_name, db)
    return calendar_id


def _ensure_user_access(service, calendar_id: str, db: Session = None):
    """Проверяет наличие доступа у пользователя, добавляет при необходимости."""
    try:
        acl_list = service.acl().list(calendarId=calendar_id).execute()
        user_emails = [
            rule["scope"].get("value")
            for rule in acl_list.get("items", [])
            if rule["scope"]["type"] == "user"
        ]
        user_email = get_user_mail_account(db)  # Передаем db
        if user_email not in user_emails:
            acl_rule = {"scope": {"type": "user", "value": user_email}, "role": "owner"}
            service.acl().insert(calendarId=calendar_id, body=acl_rule).execute()
            logging.info(f"Пользователю {user_email} предоставлен доступ к календарю.")
        else:
            logging.info(f"Пользователь {user_email} уже имеет доступ к календарю.")
    except Exception as e:
        logging.error(f"Ошибка при проверке или добавлении ACL: {e}")


def list_calendars(service):
    """Возвращает список календарей, доступных аккаунту."""
    calendars = []
    page_token = None
    while True:
        cal_list = service.calendarList().list(pageToken=page_token).execute()
        calendars.extend(cal_list.get("items", []))
        page_token = cal_list.get("nextPageToken")
        if not page_token:
            break
    return calendars


def remove_calendar(service, calendar_id: str):
    """Удаляет календарь по ID."""
    try:
        service.calendars().delete(calendarId=calendar_id).execute()
        logging.info(f"Календарь {calendar_id} удален.")
    except Exception as e:
        logging.error(f"Ошибка при удалении календаря {calendar_id}: {e}")
