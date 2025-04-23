import os
import time
import json
import logging
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import WebDriverException
from schedule_vvsu.dto.models import Lesson

# Загрузка переменных из .env
load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
LOGIN_URL = os.getenv("LOGIN_URL")
SCHEDULE_URL = os.getenv("SCHEDULE_URL")
USE_REMOTE = os.getenv("USE_REMOTE_CHROME", "false").lower() == "true"
SELENIUM_REMOTE_URL = os.getenv("SELENIUM_REMOTE_URL", "http://localhost:4444/wd/hub")

BASE_DIR = Path(__file__).resolve().parent
JSON_DIR = BASE_DIR / "json"
JSON_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
MAX_RETRIES = 3
RETRY_DELAY = 5  # секунд


def get_webdriver() -> webdriver.Firefox:
    """
    Инициализирует Firefox WebDriver (удаленный или локальный).
    """
    options = FirefoxOptions()
    options.add_argument("--headless")
    options.add_argument("--width=1280")
    options.add_argument("--height=720")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if USE_REMOTE:
                logger.info(
                    f"[{datetime.now()}] Подключение к удаленному Firefox WebDriver: {SELENIUM_REMOTE_URL} (попытка {attempt})")
                driver = webdriver.Remote(
                    command_executor=SELENIUM_REMOTE_URL,
                    options=options
                )
            else:
                logger.info(f"[{datetime.now()}] Запуск локального Firefox WebDriver (попытка {attempt})")
                driver = webdriver.Firefox(options=options)

            driver.implicitly_wait(10)
            return driver

        except WebDriverException as exc:
            logger.warning(f"[{datetime.now()}] Ошибка подключения (попытка {attempt}): {exc.msg}")
            if attempt == MAX_RETRIES:
                raise RuntimeError("Не удалось создать сессию WebDriver") from exc
            time.sleep(RETRY_DELAY)


def parse_schedule() -> list[Lesson]:
    """
    Парсит расписание из личного кабинета и возвращает список объектов Lesson.
    """
    driver = get_webdriver()
    lessons = []
    current_date = None

    try:
        print(f"[{datetime.now()}] Открываем страницу авторизации: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 30)

        # Авторизация
        login_field = wait.until(EC.presence_of_element_located((By.ID, "login")))
        password_field = wait.until(EC.presence_of_element_located((By.ID, "password")))

        print(f"[{datetime.now()}] Вводим логин и пароль.")
        login_field.send_keys(USERNAME)
        password_field.send_keys(PASSWORD)

        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Войти')]")))
        login_button.click()

        time.sleep(5)  # ожидание авторизации

        print(f"[{datetime.now()}] Переходим на страницу расписания.")
        driver.get(SCHEDULE_URL)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "carousel-inner")))
        time.sleep(5)

        print(f"[{datetime.now()}] Начинаем парсинг расписания.")
        carousel = driver.find_element(By.CLASS_NAME, "carousel-inner")
        week_elements = carousel.find_elements(By.CLASS_NAME, "carousel-item")

        for index, week in enumerate(week_elements):
            print(f"[{datetime.now()}] Парсим неделю {index + 1}/{len(week_elements)}.")
            soup = BeautifulSoup(week.get_attribute("outerHTML"), "html.parser")
            table = soup.find("table", class_="table")
            if not table:
                continue

            rows = table.find("tbody").find_all("tr")
            for row in rows:
                cols = row.find_all("td")

                if len(cols) == 1:
                    b_tag = cols[0].find("b")
                    if b_tag:
                        date_text = b_tag.get_text(strip=True).split()
                        current_date = date_text[-1] if date_text else current_date
                    continue

                if len(cols) >= 5 and current_date:
                    lessons.append(Lesson(
                        date=current_date,
                        time_range=cols[0].get_text(strip=True),
                        discipline=cols[1].get_text(strip=True),
                        teacher=cols[2].get_text(strip=True),
                        lesson_type=cols[3].get_text(strip=True),
                        auditorium=cols[4].get_text(strip=True)
                    ))

        print(f"[{datetime.now()}] Парсинг завершен. Извлечено {len(lessons)} занятий.")
        return lessons

    except Exception as e:
        print(f"[{datetime.now()}] Ошибка при парсинге: {e}")
        return []
    finally:
        driver.quit()


def save_to_json(lessons: list[Lesson], filename=None):
    """
    Сохраняет список занятий (Lesson) в JSON-файл.
    """
    filename = filename or JSON_DIR / "schedule.json"
    data = [lesson.dict() for lesson in lessons]

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"[{datetime.now()}] Расписание сохранено в {filename}")


if __name__ == "__main__":
    lessons = parse_schedule()
    if lessons:
        save_to_json(lessons)
