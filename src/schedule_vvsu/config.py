from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
from dotenv import load_dotenv
from functools import lru_cache

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)


class Settings(BaseSettings):
    # Выбор типа аккаунта: "user_account" или "service_account"
    ACCOUNT_TYPE: str = Field("user_account", env="ACCOUNT_TYPE")

    # Пути к файлам для пользовательского аккаунта (OAuth)
    USER_CREDENTIALS_FILE: str = Field(
        str(BASE_DIR / "json" / "credentials" / "user_account.json"),
        env="USER_CREDENTIALS_FILE"
    )
    USER_TOKEN_FILE: str = Field(
        str(BASE_DIR / "json" / "credentials" / "user_token.json"),
        env="USER_TOKEN_FILE"
    )

    # Путь к файлу для сервисного аккаунта (JSON-ключ)
    SERVICE_ACCOUNT_FILE: str = Field(
        str(BASE_DIR / "schedule_vvsu" / "json" / "credentials" / "service_account.json"),
        env="SERVICE_ACCOUNT_FILE"
    )

    # Настройки авторизации и парсинга
    LOGIN_URL: str = Field(..., env="LOGIN_URL")
    SCHEDULE_URL: str = Field(..., env="SCHEDULE_URL")

    # Часовой пояс по умолчанию
    TIMEZONE: str = Field("Asia/Vladivostok", env="TIMEZONE")

    # Docker-режимы
    ACTIVATE_DOCKER_TIME_SETTINGS: bool = Field(False, env="ACTIVATE_DOCKER_TIME_SETTINGS")

    # Для управления локальным / удаленным Chrome
    USE_REMOTE_CHROME: bool = Field(False, env="USE_REMOTE_CHROME")
    SELENIUM_REMOTE_URL: str = Field("http://firefox:4444/wd/hub", env="SELENIUM_REMOTE_URL")

    class Config:
        env_file = ENV_PATH
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
