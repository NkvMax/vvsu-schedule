import os
import time
import json
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from dotenv import load_dotenv

from schedule_vvsu.dto.models import Lesson  # DTO-модель

# Загрузка переменных из .env
load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
LOGIN_URL = os.getenv("LOGIN_URL")
SCHEDULE_URL = os.getenv("SCHEDULE_URL")

BASE_DIR = Path(__file__).resolve().parent
JSON_DIR = BASE_DIR / "json"
JSON_DIR.mkdir(exist_ok=True)


def parse_schedule() -> list[Lesson]:
    """
    Парсит расписание из личного кабинета и возвращает список объектов Lesson.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    lessons = []
    current_date = None

    try:
        print(f"[{datetime.now()}] Открываем страницу авторизации: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 30)

        # Поля логина и пароля
        login_field = wait.until(EC.presence_of_element_located((By.ID, "login")))
        password_field = driver.find_element(By.ID, "password")

        print(f"[{datetime.now()}] Вводим логин и пароль...")
        login_field.clear()
        login_field.send_keys(USERNAME)
        password_field.clear()
        password_field.send_keys(PASSWORD)

        # Кликаем кнопку "Войти"
        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Войти')]")))
        login_button.click()

        # Ждём авторизацию
        time.sleep(5)

        print(f"[{datetime.now()}] Переходим на страницу расписания: {SCHEDULE_URL}")
        driver.get(SCHEDULE_URL)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "carousel-inner")))
        time.sleep(5)

        print(f"[{datetime.now()}] Страница расписания загружена. Начинаем парсинг...")
        carousel = driver.find_element(By.CLASS_NAME, "carousel-inner")
        week_elements = carousel.find_elements(By.CLASS_NAME, "carousel-item")
        print(f"[{datetime.now()}] Найдено {len(week_elements)} недель расписания.")

        for index, week in enumerate(week_elements):
            print(f"[{datetime.now()}] Парсим неделю {index + 1}/{len(week_elements)}...")
            week_html = week.get_attribute("outerHTML")
            soup = BeautifulSoup(week_html, "html.parser")
            table = soup.find("table", class_="table")
            if not table:
                print(f"[{datetime.now()}] Таблица расписания не найдена в неделе {index + 1}.")
                continue

            rows = table.find("tbody").find_all("tr")
            for row in rows:
                cols = row.find_all("td")

                # Если строка содержит только одну ячейку и есть <b>, считаем, что это строка с датой
                if len(cols) == 1:
                    b_tag = cols[0].find("b")
                    if b_tag:
                        date_text = b_tag.get_text(strip=True)
                        parts = date_text.split()
                        if parts:
                            current_date = parts[-1]
                    continue

                # Если строка с занятием и есть current_date
                if len(cols) >= 5 and current_date is not None:
                    time_range = cols[0].get_text(strip=True)
                    discipline = cols[1].get_text(strip=True)
                    teacher = cols[2].get_text(strip=True)
                    lesson_type = cols[3].get_text(strip=True)
                    auditorium = cols[4].get_text(strip=True)

                    lesson = Lesson(
                        date=current_date,
                        time_range=time_range,
                        discipline=discipline,
                        lesson_type=lesson_type,
                        auditorium=auditorium,
                        teacher=teacher
                    )
                    lessons.append(lesson)

        print(f"[{datetime.now()}] Парсинг завершён. Извлечено {len(lessons)} занятий.")
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
    if filename is None:
        filename = JSON_DIR / "schedule.json"

    data = [lesson.dict() for lesson in lessons]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"[{datetime.now()}] Расписание сохранено в {filename}")


if __name__ == "__main__":
    lessons = parse_schedule()
    if lessons:
        save_to_json(lessons)
