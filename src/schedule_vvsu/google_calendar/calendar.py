import logging
from pathlib import Path
from typing import Optional
import os
from schedule_vvsu.config import settings


def get_calendar_id(service, calendar_name: str) -> Optional[str]:
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for cal in calendar_list.get('items', []):
            if cal.get('summary') == calendar_name:
                logging.info(f"Найден календарь '{calendar_name}' с ID: {cal.get('id')}")
                return cal.get('id')
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break
    logging.info(f"Календарь '{calendar_name}' не найден.")
    return None


def create_calendar(service, calendar_name: str) -> str:
    body = {
        'summary': calendar_name,
        'timeZone': settings.TIMEZONE,
        'backgroundColor': '#668BE1',  # Cobalt
        'foregroundColor': '#ffffff'
    }
    created_calendar = service.calendars().insert(body=body).execute()
    calendar_id = created_calendar.get('id')
    logging.info(f"Создан календарь: {calendar_id}")

    # Добавляем доступ для пользовательского аккаунта
    try:
        acl_rule = {
            "scope": {
                "type": "user",
                "value": settings.USER_MAIL_ACCOUNT
            },
            "role": "owner"  # Выдаем высокие привилегии
        }
        created_rule = service.acl().insert(calendarId=calendar_id, body=acl_rule).execute()
        logging.info(f"ACL правило создано: {created_rule}")
    except Exception as e:
        logging.error(f"Ошибка при установке ACL для календаря: {e}")

    return calendar_id


def get_or_create_calendar(service, calendar_name: str) -> str:
    calendar_id = get_calendar_id(service, calendar_name)
    if not calendar_id:
        logging.info(f"Создаем новый календарь '{calendar_name}'.")
        calendar_id = create_calendar(service, calendar_name)
        prev_sched_path = Path(__file__).resolve().parent.parent / "json" / "previous_schedule.json"
        if prev_sched_path.exists():
            prev_sched_path.unlink()
            logging.info("Удален previous_schedule.json для нового календаря.")
    else:
        logging.info(f"Используем существующий календарь '{calendar_name}'.")

        # Добавим здесь проверку предоставление доступа пользовательскому аккаунту, если его еще нет
        try:
            acl_list = service.acl().list(calendarId=calendar_id).execute()
            user_emails = [rule['scope'].get('value') for rule in acl_list.get('items', []) if
                           rule['scope']['type'] == 'user']
            if settings.USER_MAIL_ACCOUNT not in user_emails:
                acl_rule = {
                    "scope": {
                        "type": "user",
                        "value": settings.USER_MAIL_ACCOUNT
                    },
                    "role": "owner"
                    # максимальный уровень доступа для пользовательского аккаунта из .env (USER_MAIL_ACCOUNT)
                }
                service.acl().insert(calendarId=calendar_id, body=acl_rule).execute()
                logging.info(f"Пользователю {settings.USER_MAIL_ACCOUNT} предоставлен доступ к календарю.")
            else:
                logging.info(f"Пользователь {settings.USER_MAIL_ACCOUNT} уже имеет доступ к календарю.")
        except Exception as e:
            logging.error(f"Ошибка при проверке или добавлении ACL: {e}")

    return calendar_id


def list_calendars(service):
    """
    Возвращает список календарей, доступных аккаунту (сервисному или user-аккаунту).
    """
    calendars = []
    page_token = None
    while True:
        cal_list = service.calendarList().list(pageToken=page_token).execute()
        items = cal_list.get('items', [])
        calendars.extend(items)
        page_token = cal_list.get('nextPageToken')
        if not page_token:
            break
    return calendars


def remove_calendar(service, calendar_id: str):
    """
    Удаляет календарь по ID (владение должно быть у сервисного аккаунта).
    """
    try:
        service.calendars().delete(calendarId=calendar_id).execute()
        logging.info(f"Календарь {calendar_id} удален.")
    except Exception as e:
        logging.error(f"Ошибка при удалении календаря {calendar_id}: {e}")
