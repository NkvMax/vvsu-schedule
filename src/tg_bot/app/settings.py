from typing import Optional
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Настройки бота.

    - API_URL берется из окружения (.env или docker-compose).
    - POSTGRES_* нужны для подключения к БД (LISTEN/NOTIFY и другие).
    - BOT_TOKEN / ADMIN_IDS приходят позже через /bot/config (в виде строки!).
    """

    # URL API, откуда бот получает конфигурацию
    API_URL: AnyHttpUrl = "http://api:8000"

    # Эти поля загружаются позже из API
    BOT_TOKEN: Optional[str] = None
    ADMIN_IDS: str = ""  # Строка, например: "12345,67890"

    # Параметры подключения к Postgres
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    @property
    def DB_DSN(self) -> str:
        """DSN-строка подключения к Postgres"""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@postgres:5432/{self.POSTGRES_DB}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
