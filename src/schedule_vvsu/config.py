from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Выбор типа аккаунта: "user_account" или "service_account"
    ACCOUNT_TYPE: str = Field("user_account", env="ACCOUNT_TYPE")

    # Почта пользовательского аккаунта
    USER_MAIL_ACCOUNT: str = Field(..., env="USER_MAIL_ACCOUNT")

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
        str(BASE_DIR / "json" / "credentials" / "service_account.json"),
        env="SERVICE_ACCOUNT_FILE"
    )

    # Настройки авторизации и парсинга
    LOGIN_URL: str = Field(..., env="LOGIN_URL")
    SCHEDULE_URL: str = Field(..., env="SCHEDULE_URL")
    USERNAME: str = Field(..., env="USERNAME")
    PASSWORD: str = Field(..., env="PASSWORD")

    # Часовой пояс по умолчанию
    TIMEZONE: str = Field("Asia/Vladivostok", env="TIMEZONE")

    # Время (или интервал) синхронизации
    SYNC_TIME: str = Field("09:00", env="SYNC_TIME")
    CALENDAR_NAME: str = Field("Расписание ВВГУ", env="CALENDAR_NAME")

    # Режимы и интервалы
    DEV_MODE: bool = Field(False, env="DEV_MODE")
    ACTIVATE_DOCKER_TIME_SETTINGS: bool = Field(False, env="ACTIVATE_DOCKER_TIME_SETTINGS")
    PARSING_INTERVALS: str = Field("9:00", env="PARSING_INTERVALS")

    # Для управления локальным / удаленным Chrome
    USE_REMOTE_CHROME: bool = Field(False, env="USE_REMOTE_CHROME")
    SELENIUM_REMOTE_URL: str = Field("http://firefox:4444/wd/hub", env="SELENIUM_REMOTE_URL")

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"


settings = Settings()
