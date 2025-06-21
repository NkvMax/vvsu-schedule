from schedule_vvsu.database import get_setting, SessionLocal
from typing import Optional
from schedule_vvsu.db.models import Setting


# Получение значений
def get_user_mail_account() -> str:
    email = get_setting("USER_MAIL_ACCOUNT")
    if not email:
        raise ValueError("USER_MAIL_ACCOUNT is not set in the database.")
    return email


def get_username() -> str:
    username = get_setting("USERNAME")
    if not username:
        raise ValueError("USERNAME is not set in the database.")
    return username


def get_password() -> str:
    password = get_setting("PASSWORD")
    if not password:
        raise ValueError("PASSWORD is not set in the database.")
    return password


def get_sync_time() -> str:
    return get_setting("SYNC_TIME") or "09:00"


def get_calendar_name() -> str:
    return get_setting("CALENDAR_NAME") or "Расписание ВВГУ"


def get_parsing_intervals() -> str:
    return get_setting("PARSING_INTERVALS") or "9:00"


def get_dev_mode() -> bool:
    return get_setting("DEV_MODE") == "false"


def get_bot_enabled() -> bool:
    return get_setting("BOT_ENABLED") == "true"


def get_extra_setting_1() -> Optional[str]:
    return get_setting("EXTRA_SETTING_1")


def get_extra_setting_2() -> Optional[str]:
    return get_setting("EXTRA_SETTING_2")


# Установка значений
def set_bot_enabled(enabled: bool):
    session = SessionLocal()
    try:
        session.merge(Setting(key="BOT_ENABLED", value="true" if enabled else "false"))
        session.commit()
    finally:
        session.close()


def set_extra_setting_1(value: str):
    session = SessionLocal()
    try:
        session.merge(Setting(key="EXTRA_SETTING_1", value=value))
        session.commit()
    finally:
        session.close()


def set_extra_setting_2(value: str):
    session = SessionLocal()
    try:
        session.merge(Setting(key="EXTRA_SETTING_2", value=value))
        session.commit()
    finally:
        session.close()
