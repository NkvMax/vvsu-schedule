import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from schedule_vvsu.config import get_settings
from schedule_vvsu.database import get_setting, save_lessons_to_db

# Внутренние импорты проекта
from schedule_vvsu.dto.models import Lesson
from schedule_vvsu.logs.logger_setup import setup_logging

BASE_DIR = Path(__file__).resolve().parent

logger = logging.getLogger(__name__)
setup_logging()

MAX_RETRIES = 3
RETRY_DELAY = 5  # секунд

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
    options.headless = True
    options.add_argument("--width=1280")
    options.add_argument("--height=720")
    options.set_preference("permissions.default.image", 2)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if use_remote:
                logger.info(
                    f"[{datetime.now()}] Подключение к удаленному WebDriver: {remote_url}"
                )
                return webdriver.Remote(command_executor=remote_url, options=options)
            else:
                logger.info(f"[{datetime.now()}] Запуск локального Firefox WebDriver")
                return webdriver.Firefox(options=options)
        except WebDriverException as exc:
            logger.warning(
                f"[{datetime.now()}] Ошибка подключения (попытка {attempt}): {exc.msg}"
            )
            if attempt == MAX_RETRIES:
                raise RuntimeError("Не удалось создать сессию WebDriver") from exc
            time.sleep(RETRY_DELAY)


def wait_for_carousel_items(driver, timeout=30, poll_frequency=1):
    """Ждем, пока появятся элементы .carousel-item внутри .carousel-inner."""
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


def _normalize_url(raw: str) -> Optional[str]:
    if not raw:
        return None
    href = raw.strip()
    # Пропускаем JavaScript/якоря
    if href.startswith("#") or href.lower().startswith("javascript:"):
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    # "Голая" ссылка без схемы
    if "." in href:
        return "https://" + href.lstrip("/")
    return None


def _find_webinar_url(cell) -> Optional[str]:
    """
    Ищем ссылку на вебинар внутри ячейки дисциплины:
    - любые <a href="...">;
    - если href без схемы — добавим https://;
    - отдаем первую подходящую.
    """
    for a in cell.find_all("a", href=True):
        href = _normalize_url(a["href"])
        if not href:
            continue
        # Часто домен ktalk/vvsu — но не ограничиваемся только им
        return href

    # Иногда URL лежит просто текстом в ячейке после 'вебинар:'
    import re

    txt = cell.get_text(" ", strip=True)
    m = re.search(r"(https?://\S+|\b[\w.-]+\.[a-z]{2,}/\S+)", txt, flags=re.I)
    if m:
        return _normalize_url(m.group(1))
    return None


def _extract_subject(cell) -> str:
    """
    Название дисциплины:
    - если есть ссылка на '/time-table/dis' — берем ее текст (без вложенных 'вебинар:' кусков);
    - иначе пробуем <b>;
    - иначе — общий текст ячейки с удалением хвоста 'вебинар: ...'.
    """
    # 1) целевая ссылка со страницей дисциплины
    for a in cell.find_all("a", href=True):
        if "/time-table/dis" in a.get("href", ""):
            text = a.get_text(" ", strip=True)
            if text:
                return text

    # 2) иногда название обернуто <b>
    b = cell.find("b")
    if b:
        txt = b.get_text(" ", strip=True)
        if txt:
            return txt

    # 3) fallback: общий текст без хоста вебинара
    full = cell.get_text(" ", strip=True)
    import re

    full = re.sub(
        r"вебинар\s*:.*$", "", full, flags=re.I
    )  # отрезаем хвост 'вебинар: ...'
    return full.strip()


def parse_schedule() -> List[Lesson]:
    cfg = get_config()

    driver = get_webdriver(cfg["USE_REMOTE"], cfg["SELENIUM_REMOTE_URL"])
    lessons: List[Lesson] = []
    current_date = None

    try:
        logger.info("Открываем страницу авторизации.")
        driver.get(cfg["LOGIN_URL"])
        wait = WebDriverWait(driver, 30)

        login_field = wait.until(EC.presence_of_element_located((By.ID, "login")))
        password_field = wait.until(EC.presence_of_element_located((By.ID, "password")))

        logger.info("Вводим логин и пароль.")
        login_field.send_keys(cfg["USERNAME"])
        password_field.send_keys(cfg["PASSWORD"])

        login_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Войти')]"))
        )
        login_button.click()

        logger.info("Переходим на страницу расписания.")
        time.sleep(10)
        driver.get(cfg["SCHEDULE_URL"])

        # немножко прокрутим, чтобы сработала подгрузка
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "carousel-inner")))

        logger.info("Ждем появления расписания...")
        week_elements = wait_for_carousel_items(driver)

        if not week_elements:
            logger.warning(
                "Расписание сейчас недоступно — возможно, учебный семестр завершен."
            )
            try:
                with open(BASE_DIR / "error.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                driver.save_screenshot(str(BASE_DIR / "error.png"))
            except Exception:
                pass
            return []

        logger.info("Начинаем парсинг расписания.")
        for index, week in enumerate(week_elements):
            logger.info(f"Парсим неделю {index + 1}/{len(week_elements)}.")
            soup = BeautifulSoup(week.get_attribute("outerHTML"), "html.parser")
            table = soup.find("table", class_="table")
            if not table:
                continue

            tbody = table.find("tbody")
            if not tbody:
                continue
            rows = tbody.find_all("tr")

            for row in rows:
                cols = row.find_all("td")
                if len(cols) == 1:
                    # строка с датой: <b>Вторник 16.09.2025</b>
                    b_tag = cols[0].find("b")
                    if b_tag:
                        parts = b_tag.get_text(strip=True).split()
                        current_date = parts[-1] if parts else current_date
                    continue

                if len(cols) >= 5 and current_date:
                    time_cell = cols[0]
                    disc_cell = cols[1]
                    teacher_cell = cols[2]
                    type_cell = cols[3]
                    room_cell = cols[4]

                    # Время "18:30-20:00"
                    time_range = time_cell.get_text(strip=True)

                    subject = _extract_subject(disc_cell)
                    webinar_url = _find_webinar_url(disc_cell)

                    teacher = teacher_cell.get_text(strip=True)
                    lesson_type = type_cell.get_text(strip=True)
                    room = room_cell.get_text(strip=True)

                    # Если нашли ссылку — добавим ее в subject хвостом 'вебинар:<url>'
                    # (это гарантирует, что ссылка дойдет до БД даже если у модели нет поля webinar_url)
                    if webinar_url and ("вебинар:" not in subject):
                        subject = f"{subject} вебинар:{webinar_url}"

                    # Модель Lesson в проекте принимает поля вида 'date/time_range/discipline/teacher/lesson_type/auditorium'
                    # Дальше маппер в БД преобразует: discipline->subject, time_range->start/end, auditorium->room
                    lesson = Lesson(
                        date=current_date,
                        time_range=time_range,
                        discipline=subject,
                        teacher=teacher,
                        lesson_type=lesson_type,
                        auditorium=room,
                    )
                    lessons.append(lesson)

        logger.info(f"Парсинг завершен. Извлечено занятий: {len(lessons)}")
        return lessons

    except Exception as e:
        logger.exception(f"Ошибка при парсинге: {e}")
        try:
            with open(BASE_DIR / "error.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot(str(BASE_DIR / "error.png"))
        except Exception:
            pass
        return []
    finally:
        driver.quit()


if __name__ == "__main__":
    lessons = parse_schedule()
    if lessons:
        save_lessons_to_db(lessons)
