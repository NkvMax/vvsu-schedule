import os
import logging
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from schedule_vvsu.config import settings

SCOPES = ['https://www.googleapis.com/auth/calendar']

# Преобразуем пути из настроек в объекты Path
USER_CREDENTIALS_FILE = Path(settings.USER_CREDENTIALS_FILE)
USER_TOKEN_FILE = Path(settings.USER_TOKEN_FILE)
SERVICE_ACCOUNT_FILE = Path(settings.SERVICE_ACCOUNT_FILE)


def authenticate_user_account():
    """
    Аутентификация через пользовательский аккаунт (OAuth).
    Использует файл USER_CREDENTIALS_FILE для client_id и client_secret, а USER_TOKEN_FILE для хранения токена.
    """
    creds = None
    if USER_TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(USER_TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logging.info("Токен обновлен через refresh_token.")
            except Exception as e:
                logging.error(f"Ошибка при обновлении токена: {e}")
                flow = InstalledAppFlow.from_client_secrets_file(str(USER_CREDENTIALS_FILE), SCOPES)
                creds = flow.run_local_server(port=0)
                logging.info("Токен получен (повторная полная аутентификация).")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(USER_CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
            logging.info("Токен получен (полная аутентификация).")
        with USER_TOKEN_FILE.open("w") as token:
            token.write(creds.to_json())
            logging.info(f"Токен сохранен в {USER_TOKEN_FILE}.")
    return creds


def authenticate_service_account():
    """
    Аутентификация через сервисный аккаунт.
    Использует SERVICE_ACCOUNT_FILE.
    """
    creds = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
    )
    return creds


def authenticate_google_calendar():
    """
    Фабричный метод для выбора метода аутентификации в зависимости от настроек.
    """
    if settings.ACCOUNT_TYPE == "service_account":
        logging.info("Используется сервисный аккаунт.")
        creds = authenticate_service_account()
    elif settings.ACCOUNT_TYPE == "user_account":
        logging.info("Используется пользовательский аккаунт.")
        creds = authenticate_user_account()
    else:
        raise ValueError("Неверный тип аккаунта в настройках (ACCOUNT_TYPE).")
    from googleapiclient.discovery import build
    service = build('calendar', 'v3', credentials=creds)
    return service
