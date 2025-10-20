import os
import re
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

# env 
LOGIN_URL = os.getenv("LOGIN_URL", "https://cabinet.vvsu.ru/")
SCHEDULE_URL = os.getenv("SCHEDULE_URL", "https://cabinet.vvsu.ru/time-table/")
USER = os.getenv("VVSU_LOGIN", "")
PASS = os.getenv("VVSU_PASSWORD", "")

HEADLESS = os.getenv("PW_HEADLESS", "1") == "1"
TIMEOUT_MS = int(os.getenv("PW_TIMEOUT_MS", "20000"))
SLEEP_AFTER = float(os.getenv("PW_SLEEP_AFTER", "0"))
MAX_WEEKS_AHEAD = int(os.getenv("MAX_WEEKS_AHEAD", "8"))
MAX_WEEKS_BACK = int(os.getenv("MAX_WEEKS_BACK", "0"))

def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _extract_webinar(cell) -> Optional[str]:
    # прямая ссылка <a href="...">
    for a in cell.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("//"):
            href = "https:" + href
        if href.startswith("http"):
            return href
        # голая ссылка вида vvsu.ktalk.ru/xxx
        if "." in href and "/" in href:
            return "https://" + href.lstrip("/")
    # текст "вебинар: ..."
    m = re.search(r"(https?://\S+|\b[\w.-]+\.[a-z]{2,}/\S+)", cell.get_text(" ", strip=True), flags=re.I)
    if m:
        href = m.group(1).strip()
        if not href.startswith("http"):
            href = "https://" + href
        return href
    return None

def _extract_subject(cell) -> str:
    # предпочитаем ссылку на /time-table/dis
    for a in cell.find_all("a", href=True):
        if "/time-table/dis" in a["href"]:
            txt = a.get_text(" ", strip=True)
            if txt:
                return txt
    # bold
    b = cell.find("b")
    if b:
        txt = b.get_text(" ", strip=True)
        if txt:
            return txt
    # иначе — общий текст без хвоста "вебинар: ..."
    txt = cell.get_text(" ", strip=True)
    txt = re.sub(r"вебинар\s*:.*$", "", txt, flags=re.I).strip()
    return txt

def _lesson_type(cell) -> str:
    t = _norm_text(cell.get_text(" ", strip=True)).lower()
    # нормализация
    if "лекц" in t:
        return "лекция"
    if "прак" in t or "семинар" in t or "вебинар" in t:
        if "вебинар" in t:
            return "вебинар"
        return "практика"
    return t or ""

def _parse_week_html(html: str, logger: logging.Logger) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.table, table.table-cabinet, table.table-responsive-md table")
    if not table:
        return []
    tbody = table.find("tbody") or table
    rows = tbody.find_all("tr")
    lessons: List[Dict] = []
    current_date: Optional[str] = None

    for tr in rows:
        tds = tr.find_all("td")
        if not tds:
            continue
        # строка с датой: одна ячейка и там <b>Понедельник 20.10.2025</b>
        if len(tds) == 1:
            b = tds[0].find("b")
            if b:
                parts = _norm_text(b.get_text(" ", strip=True)).split()
                if parts:
                    current_date = parts[-1]
            continue

        if len(tds) >= 5 and current_date:
            time_range = _norm_text(tds[0].get_text())
            subject = _extract_subject(tds[1])
            webinar = _extract_webinar(tds[1])
            teacher = _norm_text(tds[2].get_text())
            ltype = _lesson_type(tds[3])
            room = _norm_text(tds[4].get_text())
            if time_range and subject:
                lessons.append({
                    "date": current_date,
                    "time_range": time_range,
                    "discipline": subject,
                    "teacher": teacher,
                    "lesson_type": ltype,
                    "auditorium": room,
                    "webinar_url": webinar,
                })
    return lessons

def _parse_all_carousel_items(page, logger: logging.Logger) -> List[Dict]:
    # В bootstrap-карусели все .carousel-item присутствуют в DOM читаем их все без кликов
    items = page.locator(".carousel-inner .carousel-item").all()
    if not items:
        logger.warning("Карусель не найдена, фолбэк к парсингу всей страницы")
        return _parse_week_html(page.content(), logger)

    all_lessons: List[Dict] = []
    weeks = 0
    for it in items:
        html = it.inner_html()
        week_lessons = _parse_week_html(html, logger)
        if week_lessons:
            weeks += 1
            all_lessons.extend(week_lessons)
    logger.info("Из карусели прочитали недель: %d", weeks)
    return all_lessons

def _dedup(lessons: List[Dict]) -> List[Dict]:
    seen = set()
    res = []
    for l in lessons:
        key = (l["date"], l["time_range"], l["discipline"], l.get("teacher",""), l.get("lesson_type",""), l.get("auditorium",""), l.get("webinar_url") or "")
        if key in seen:
            continue
        seen.add(key)
        res.append(l)
    return res

def fetch_lessons(logger: logging.Logger) -> List[Dict]:
    """
    Полный, устойчивый парсинг:
    - логин по прямому URL;
    - переход на страницу расписания по прямой ссылке;
    - чтение всех .carousel-item в DOM, без кликов (устойчиво к кнопкам);
    - фолбэк: если карусели не видно, парсим всю страницу как одну неделю.
    """
    if not USER or not PASS:
        raise RuntimeError("Заполните VVSU_LOGIN и VVSU_PASSWORD")

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=HEADLESS)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        logger.info("Открываем страницу логина..")
        page.goto(LOGIN_URL)
        # поля логина/пароля — набор стратегий
        login_selector = "[id='login'], input[name='login'], input[placeholder*='логин' i]"
        pass_selector = "[id='password'], input[name='password'], input[placeholder*='пароль' i]"
        page.locator(login_selector).first.fill(USER)
        page.locator(pass_selector).first.fill(PASS)

        # разные варианты кнопки
        candidates = [
            "//button[contains(., 'Войти')]",
            "button[type='submit']",
            "text=Войти",
        ]
        clicked = False
        for sel in candidates:
            try:
                page.locator(sel).first.click(timeout=3000)
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            page.keyboard.press("Enter")

        # после логина — прямо на расписание
        page.wait_for_load_state("networkidle", timeout=15000)
        logger.info("Открываем страницу расписания: %s", SCHEDULE_URL)
        page.goto(SCHEDULE_URL)
        try:
            page.wait_for_selector(".carousel-inner, table.table", timeout=10000)
        except PwTimeout:
            pass

        # собираем все недели из DOM
        lessons = _parse_all_carousel_items(page, logger)
        if not lessons:
            # еще одна попытка: чуть подождать и перечитать
            page.wait_for_timeout(800)
            lessons = _parse_all_carousel_items(page, logger)

        lessons = _dedup(lessons)
        # простой диапазон дат
        dates_dt = sorted({datetime.strptime(l["date"], "%d.%m.%Y") for l in lessons})
        if dates_dt:
            unique_weeks = len({(d.isocalendar().year, d.isocalendar().week) for d in dates_dt})
            logger.info(
                "Парсинг завершен: weeks=%d, days=%d, lessons=%d, date_range=%s..%s",
                unique_weeks, len(dates_dt), len(lessons),
                dates_dt[0].strftime("%d.%m.%Y"),
                dates_dt[-1].strftime("%d.%m.%Y"),
            )
        else:
            logger.warning("Парсинг завершен: занятий не найдено")

        if SLEEP_AFTER:
            page.wait_for_timeout(int(SLEEP_AFTER * 1000))

        ctx.close()
        browser.close()
        return lessons
