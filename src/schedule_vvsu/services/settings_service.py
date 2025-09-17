from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from schedule_vvsu.database import SessionLocal, get_db, get_setting
from schedule_vvsu.db.models import Setting


# Получение значений
def get_user_mail_account(db: Session = Depends(get_db)) -> str:
    email = db.query(Setting).filter_by(key="USER_MAIL_ACCOUNT").first()
    if not email:
        raise ValueError("USER_MAIL_ACCOUNT is not set in the database.")
    return email.value


def get_username(db: Session = Depends(get_db)) -> str:
    username = db.query(Setting).filter_by(key="USERNAME").first()
    if not username:
        raise ValueError("USERNAME is not set in the database.")
    return username.value


def get_password(db: Session = Depends(get_db)) -> str:
    password = db.query(Setting).filter_by(key="PASSWORD").first()
    if not password:
        raise ValueError("PASSWORD is not set in the database.")
    return password.value


def get_sync_time(db: Session = Depends(get_db)) -> str:
    return (
        db.query(Setting).filter_by(key="SYNC_TIME").first().value
        if db.query(Setting).filter_by(key="SYNC_TIME").first()
        else "09:00"
    )


def get_calendar_name(db: Session = Depends(get_db)) -> str:
    """
    Получает имя календаря из настроек базы данных или возвращает дефолт.
    """
    setting = db.query(Setting).filter_by(key="CALENDAR_NAME").first()
    return setting.value if setting else "VVSU Schedule"


def get_parsing_intervals(db: Session = Depends(get_db)) -> str:
    return (
        db.query(Setting).filter_by(key="PARSING_INTERVALS").first().value
        if db.query(Setting).filter_by(key="PARSING_INTERVALS").first()
        else "9:00"
    )


def get_dev_mode(db: Session = Depends(get_db)) -> bool:
    return (
        db.query(Setting).filter_by(key="DEV_MODE").first().value == "false"
        if db.query(Setting).filter_by(key="DEV_MODE").first()
        else False
    )


def get_bot_enabled(db: Session = Depends(get_db)) -> bool:
    return (
        db.query(Setting).filter_by(key="BOT_ENABLED").first().value == "true"
        if db.query(Setting).filter_by(key="BOT_ENABLED").first()
        else False
    )


def get_extra_setting_1(db: Session = Depends(get_db)) -> Optional[str]:
    return (
        db.query(Setting).filter_by(key="EXTRA_SETTING_1").first().value
        if db.query(Setting).filter_by(key="EXTRA_SETTING_1").first()
        else None
    )


def get_extra_setting_2(db: Session = Depends(get_db)) -> Optional[str]:
    return (
        db.query(Setting).filter_by(key="EXTRA_SETTING_2").first().value
        if db.query(Setting).filter_by(key="EXTRA_SETTING_2").first()
        else None
    )


# Установка значений
def set_bot_enabled(enabled: bool, db: Session = Depends(get_db)):
    db.merge(Setting(key="BOT_ENABLED", value="true" if enabled else "false"))
    db.commit()


def set_extra_setting_1(value: str, db: Session = Depends(get_db)):
    db.merge(Setting(key="EXTRA_SETTING_1", value=value))
    db.commit()


def set_extra_setting_2(value: str, db: Session = Depends(get_db)):
    db.merge(Setting(key="EXTRA_SETTING_2", value=value))
    db.commit()
