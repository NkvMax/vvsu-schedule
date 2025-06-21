import time
import logging
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import WebDriverException

from schedule_vvsu.dto.models import Lesson
from schedule_vvsu.database import save_lessons_to_db, get_setting
from schedule_vvsu.logs.logger_setup import setup_logging
from schedule_vvsu.config import get_settings

BASE_DIR = Path(__file__).resolve().parent

# Настройка логирования
logger = logging.getLogger(__name__)
setup_logging()

# Константы
MAX_RETRIES = 3
RETRY_DELAY = 5  # секунд

# Настройки из .env
settings = get_settings()


def get_config():
    return {
        "USERNAME": get_setting("USERNAME"),
        "PASSWORD": get_setting("PASSWORD"),
        "LOGIN_URL": settings.LOGIN_URL,
        "SCHEDULE_URL": settings.SCHEDULE_URL,
        "USE_REMOTE": settings.USE_REMOTE_CHROME,
        "SELENIUM_REMOTE_URL": settings.SELENIUM_REMOTE_URL,
    }


def get_webdriver(use_remote: bool, remote_url: str) -> webdriver.Firefox:
    options = FirefoxOptions()
    options.add_argument("--headless")
    options.add_argument("--width=1280")
    options.add_argument("--height=720")
    options.set_preference("permissions.default.image", 2)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if use_remote:
                logger.info(f"[{datetime.now()}] Подключение к удаленному WebDriver: {remote_url}")
                return webdriver.Remote(command_executor=remote_url, options=options)
            else:
                logger.info(f"[{datetime.now()}] Запуск локального Firefox WebDriver")
                return webdriver.Firefox(options=options)
        except WebDriverException as exc:
            logger.warning(f"[{datetime.now()}] Ошибка подключения (попытка {attempt}): {exc.msg}")
            if attempt == MAX_RETRIES:
                raise RuntimeError("Не удалось создать сессию WebDriver") from exc
            time.sleep(RETRY_DELAY)


def wait_for_carousel_items(driver, timeout=30, poll_frequency=1):
    """
    Ждем, пока появятся элементы .carousel-item внутри .carousel-inner
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            carousel = driver.find_element(By.CLASS_NAME, "carousel-inner")
            items = carousel.find_elements(By.CLASS_NAME, "carousel-item")
            if items:
                return items
        except Exception:
            pass
        time.sleep(poll_frequency)
    return []


def parse_schedule() -> list[Lesson]:
    config = get_config()

    USERNAME = config["USERNAME"]
    PASSWORD = config["PASSWORD"]
    LOGIN_URL = config["LOGIN_URL"]
    SCHEDULE_URL = config["SCHEDULE_URL"]
    USE_REMOTE = config["USE_REMOTE"]
    SELENIUM_REMOTE_URL = config["SELENIUM_REMOTE_URL"]

    driver = get_webdriver(USE_REMOTE, SELENIUM_REMOTE_URL)
    lessons = []
    current_date = None

    try:
        logger.info("Открываем страницу авторизации.")
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 30)

        login_field = wait.until(EC.presence_of_element_located((By.ID, "login")))
        password_field = wait.until(EC.presence_of_element_located((By.ID, "password")))

        logger.info("Вводим логин и пароль.")
        login_field.send_keys(USERNAME)
        password_field.send_keys(PASSWORD)

        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Войти')]")))
        login_button.click()

        logger.info("Переходим на страницу расписания.")
        time.sleep(10)
        driver.get(SCHEDULE_URL)

        # Прокручиваем вниз, чтобы отрисовалась карусель
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "carousel-inner")))

        logger.info("Ждем появления расписания...")
        week_elements = wait_for_carousel_items(driver)

        if not week_elements:
            logger.warning("Расписание сейчас недоступно — возможно, учебный семестр завершен.")
            logger.warning("Сохраняю HTML и скриншот страницы для анализа.")
            with open(BASE_DIR / "error.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot(str(BASE_DIR / "error.png"))
            return []

        logger.info("Начинаем парсинг расписания.")
        for index, week in enumerate(week_elements):
            logger.info(f"Парсим неделю {index + 1}/{len(week_elements)}.")
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

        logger.info(f"Парсинг завершен. Извлечено занятий: {len(lessons)}")
        return lessons

    except Exception as e:
        logger.exception(f"Ошибка при парсинге: {e}")
        with open(BASE_DIR / "error.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        driver.save_screenshot(str(BASE_DIR / "error.png"))
        return []

    finally:
        driver.quit()


if __name__ == "__main__":
    lessons = parse_schedule()
    if lessons:
        save_lessons_to_db(lessons)
