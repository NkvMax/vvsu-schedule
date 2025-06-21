from pathlib import Path
from fastapi import FastAPI, Form, UploadFile, File, APIRouter, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import subprocess
import signal
import os
from typing import Optional, Dict
from signal import SIGTERM
import logging
from threading import Thread

from schedule_vvsu.config import get_settings
from schedule_vvsu.parser import parse_schedule
from schedule_vvsu.database import save_lessons_to_db, init_db, SessionLocal
from schedule_vvsu.google_calendar.auth import authenticate_google_calendar
from schedule_vvsu.google_calendar.calendar import get_or_create_calendar
from schedule_vvsu.google_calendar.sync import sync_schedule_to_calendar
from schedule_vvsu.db.models import LogEntry, Setting
from schedule_vvsu.logs.logger_setup import setup_logging
from schedule_vvsu.db.models import SchedulerStatus, ParseRun
from schedule_vvsu.services.settings_service import get_parsing_intervals
from schedule_vvsu.scheduler import record_parse_run
from sqlalchemy import desc
from schedule_vvsu.auth import router as auth_router
from datetime import datetime, timedelta, date
from sqlalchemy import func

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from schedule_vvsu.database import get_db

settings = get_settings()
setup_logging()
logger = logging.getLogger("cli_logger")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCHEDULER_PID_FILE = BASE_DIR / "scheduler.pid"
CURRENT_PID = os.getpid()
LOG_DIR = BASE_DIR / "src" / "schedule_vvsu" / "logs"
LOG_PATH = LOG_DIR / "sync_log.log"
CREDENTIALS_PATH = BASE_DIR / "src" / "schedule_vvsu" / "json" / "credentials"
FRONTEND_DIST = BASE_DIR / "src" / "frontend" / "dist"

bot_router = APIRouter(prefix="/bot", tags=["bot"])

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter()


@app.get("/healthz", include_in_schema=False)
def healthcheck():
    return {"status": "ok"}


# Helper
def _pid_running(pid: int) -> bool:
    """True, если процесс с данным PID еще жив."""
    try:
        os.kill(pid, 0)  # проверка без посылки сигнала
        return True
    except OSError:
        return False


# Health check
@api_router.get("/health")
async def health():
    return {"status": "ok"}


# Проверка базовой настройки
@api_router.get("/config/status")
async def config_status():
    session = SessionLocal()
    has_username = session.query(Setting).filter_by(key="USERNAME").first()
    has_password = session.query(Setting).filter_by(key="PASSWORD").first()
    session.close()
    return {"configured": bool(has_username and has_password)}


# Получение логов из БД
@api_router.get("/logs/sql")
async def get_sql_logs(after_id: int = 0):
    session = SessionLocal()
    try:
        entries = session.query(LogEntry).filter(LogEntry.id > after_id).order_by(LogEntry.id).limit(100).all()
        return [
            {"id": e.id, "ts": e.timestamp.isoformat(), "level": e.level, "msg": e.message}
            for e in entries
        ]
    finally:
        session.close()


# Получение настроек
@api_router.get("/account")
async def get_account():
    session = SessionLocal()
    try:
        settings = session.query(Setting).all()
        return {s.key: s.value for s in settings}
    finally:
        session.close()


# Обновление / установка настроек
@api_router.post("/account")
async def update_account(
        username: str = Form(...),
        password: str = Form(...),
        user_mail_account: str = Form(...),
        parsing_intervals: str = Form(...),
        calendar_name: str = Form(...),
        file: UploadFile = File(None)
):
    session = SessionLocal()

    def upsert(key, value):
        setting = session.query(Setting).filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            session.add(Setting(key=key, value=value))

    upsert("USERNAME", username)
    upsert("PASSWORD", password)
    upsert("USER_MAIL_ACCOUNT", user_mail_account)
    upsert("PARSING_INTERVALS", parsing_intervals)
    upsert("CALENDAR_NAME", calendar_name)

    if file:
        CREDENTIALS_PATH.mkdir(parents=True, exist_ok=True)
        with open(CREDENTIALS_PATH / "service_account.json", "wb") as f:
            f.write(await file.read())

    session.commit()
    session.close()
    return {"ok": True}


# Первичная установка
@api_router.post("/setup")
async def setup(
        username: str = Form(...),
        password: str = Form(...),
        user_mail_account: str = Form(...),
        parsing_intervals: str = Form(...),
        calendar_name: str = Form(...),
        file: UploadFile = File(...)
):
    return await update_account(username, password, user_mail_account, parsing_intervals, calendar_name, file)


# Синхронизация вручную
@api_router.post("/sync")
async def sync_now():
    def run_sync():
        logger.info("Ручной запуск синхронизации через API.")
        record_parse_run("started", "ручной запуск синхронизации")

        try:
            # парсим расписание
            init_db()
            schedule = parse_schedule()

            if not schedule:
                msg = "Не удалось получить расписание."
                logger.warning(msg)
                record_parse_run("error", msg)
                return

            # сохраняем в БД и Google Calendar
            save_lessons_to_db(schedule)
            service = authenticate_google_calendar()
            calendar_id = get_or_create_calendar(service, settings.CALENDAR_NAME)
            sync_schedule_to_calendar(service, schedule, calendar_id)

            # финальная запись об успехе
            ok_msg = f"синхронизировано {len(schedule)} занятий"
            logger.info(ok_msg)
            record_parse_run("success", ok_msg)

        except Exception as e:
            err_msg = f"Ошибка во время синхронизации: {e}"
            logger.exception(err_msg)
            record_parse_run("error", err_msg[:250])  # ограничиваем длину деталей

    # запускаем синхронизацию в отдельном потоке,
    # чтобы не блокировать ответ API
    Thread(target=run_sync, daemon=True).start()
    return {"synced": "started", "details": "Синхронизация выполняется в фоне"}


# Запуск планировщика
@api_router.post("/scheduler/start")
async def start_scheduler():
    if SCHEDULER_PID_FILE.exists():
        pid = int(SCHEDULER_PID_FILE.read_text())

        # битый PID указывает на текущий uvicorn-процесс
        if pid == CURRENT_PID:
            logger.warning("Старый PID-файл с PID текущего сервера — удаляю.")
            SCHEDULER_PID_FILE.unlink(missing_ok=True)
        elif _pid_running(pid):
            logger.info("Попытка повторного запуска — планировщик уже работает.")
            return {"scheduler": "already running", "pid": pid}
        else:
            # зомби PID
            SCHEDULER_PID_FILE.unlink(missing_ok=True)

    proc = subprocess.Popen(
        ["python", "-m", "schedule_vvsu.scheduler"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    SCHEDULER_PID_FILE.write_text(str(proc.pid))
    logger.info(f"Планировщик запущен, PID={proc.pid}")
    return {"scheduler": "started", "pid": proc.pid}


# Остановка планировщика
@api_router.post("/scheduler/stop")
async def stop_scheduler():
    if not SCHEDULER_PID_FILE.exists():
        return {"scheduler": "already stopped"}

    pid = int(SCHEDULER_PID_FILE.read_text())

    # если PID указывает на uvicorn — не убиваем сервер
    if pid == CURRENT_PID:
        logger.warning("PID-файл указывает на API-процесс — просто очищаю файл.")
        SCHEDULER_PID_FILE.unlink(missing_ok=True)
        return {"scheduler": "stopped (stale pid removed)"}

    try:
        if _pid_running(pid):
            os.kill(pid, signal.SIGTERM)
            logger.info(f"SIGTERM отправлен, PID={pid}")
        else:
            logger.warning("Процесс планировщика уже не существует.")
    finally:
        SCHEDULER_PID_FILE.unlink(missing_ok=True)

    return {"scheduler": "stopped"}


# Логи синхронизации
@api_router.get("/logs/sync")
async def get_sync_logs():
    if not LOG_PATH.exists():
        return JSONResponse(status_code=404, content={"error": "Log file not found"})

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()[-50:]
    return {"logs": lines[::-1]}


# Общие логи
@api_router.get("/logs/combined")
async def get_combined_logs():
    log_files = list(LOG_DIR.glob("*.log"))
    all_lines = []

    for path in log_files:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                all_lines.extend(line.strip() for line in f)

    def extract_timestamp(line):
        try:
            return line.split(" ", 2)[0] + " " + line.split(" ", 2)[1]
        except IndexError:
            return "0000-00-00 00:00:00"

    sorted_lines = sorted(all_lines, key=extract_timestamp, reverse=True)
    return {"logs": sorted_lines[:100]}


@api_router.get("/scheduler/status")
async def scheduler_status():
    if SCHEDULER_PID_FILE.exists():
        pid = int(SCHEDULER_PID_FILE.read_text())
        return {"status": "running" if _pid_running(pid) and pid != CURRENT_PID else "stopped",
                "pid": pid}
    return {"status": "stopped"}


@api_router.get("/scheduler/timeline")
async def scheduler_timeline(days: int = 30):
    """Возвращает массив за N дней: [{date, status, message?}]"""
    session = SessionLocal()
    try:
        today = date.today()
        result = []

        for shift in range(days):
            d0 = today - timedelta(days=shift)
            d1 = d0 + timedelta(days=1)

            rows = (session.query(ParseRun.status, func.count())
                    .filter(ParseRun.timestamp >= d0,
                            ParseRun.timestamp < d1)
                    .group_by(ParseRun.status)
                    .all())

            if not rows:
                result.append({"date": d0.isoformat(),
                               "status": "error",
                               "message": "нет запусков"})
                continue

            has_err = any(s in ("error",) for s, _ in rows)
            has_ok = any(s in ("success", "done") for s, _ in rows)

            status = "ok" if has_ok and not has_err else \
                "warn" if has_ok and has_err else "error"

            result.append({"date": d0.isoformat(), "status": status})

        return list(reversed(result))  # старые → новые
    finally:
        session.close()


@api_router.get("/scheduler/overview")
async def scheduler_overview():
    session = SessionLocal()
    try:
        # статус планировщика
        st_entry = (session.query(SchedulerStatus)
                    .order_by(desc(SchedulerStatus.updated_at))
                    .first())
        status = st_entry.status if st_entry else "stopped"

        # интервалы из настроек
        intervals = [t.strip() for t in get_parsing_intervals().split(",") if t.strip()]

        # последние прогоны
        runs_q = (session.query(ParseRun)
                  .order_by(desc(ParseRun.timestamp))
                  .limit(20)
                  .all())
        runs = [{
            "time": r.time_str,
            "status": r.status,
            "detail": r.detail
        } for r in runs_q]

        return {"status": status, "intervals": intervals, "runs": runs}
    finally:
        session.close()


class BotConfigPatch(BaseModel):
    bot_token: Optional[str] = None  # может быть пустым -> бот выключится
    admin_ids: Optional[str] = None  # CSV или JSON-строка


def _get_setting(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    rec = db.query(Setting).filter_by(key=key).first()
    return rec.value if rec else default


@bot_router.get("/config")
def bot_config(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Текущие настройки бота (без авторизации — контейнеры в одной сети)."""
    return {
        "bot_token": _get_setting(db, "BOT_TOKEN") or "",
        "admin_ids": _get_setting(db, "ADMIN_IDS") or "",
    }


@bot_router.patch("/config")
def update_bot_config(
        patch: BotConfigPatch,
        db: Session = Depends(get_db)
) -> Dict[str, bool]:
    """Обновить BOT_TOKEN / ADMIN_IDS без перезапуска контейнера."""
    for field, value in patch.dict(exclude_none=True).items():
        rec = db.query(Setting).filter_by(key=field.upper()).first()
        if rec:
            rec.value = value or ""
        else:
            db.add(Setting(key=field.upper(), value=value or ""))
    db.commit()
    db.execute(text("NOTIFY bot_config, 'reload';"))
    return {"ok": True}


# Раздача статики
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


class BotSettings(BaseModel):
    bot_enabled: Optional[bool] = None
    extra_setting_1: Optional[str] = None
    extra_setting_2: Optional[str] = None


@bot_router.get("/settings")
def get_bot_settings(db: Session = Depends(get_db)):
    return {
        "bot_enabled": _get_setting(db, "BOT_ENABLED", "false") == "true",
        "extra_setting_1": _get_setting(db, "EXTRA_SETTING_1"),
        "extra_setting_2": _get_setting(db, "EXTRA_SETTING_2"),
    }


def _upsert_setting(db: Session, key: str, value: str) -> None:
    rec = db.query(Setting).filter_by(key=key).first()
    if rec:
        rec.value = value
    else:
        db.add(Setting(key=key, value=value))


@bot_router.post("/settings")
def update_bot_settings(settings: BotSettings, db: Session = Depends(get_db)):
    if settings.bot_enabled is not None:
        _upsert_setting(db, "BOT_ENABLED", "true" if settings.bot_enabled else "false")
    if settings.extra_setting_1 is not None:
        _upsert_setting(db, "EXTRA_SETTING_1", settings.extra_setting_1)
    if settings.extra_setting_2 is not None:
        _upsert_setting(db, "EXTRA_SETTING_2", settings.extra_setting_2)

    db.commit()
    db.execute(text("NOTIFY bot_config, 'reload';"))
    return {"status": "ok"}


# Подключение API
app.include_router(api_router, prefix="/api")  # основные пути
app.include_router(bot_router)
app.include_router(
    bot_router,
    prefix="/api",
    include_in_schema=False
)

app.include_router(auth_router)


@app.get("/", response_class=HTMLResponse)
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def spa(full_path: str = ""):
    if full_path.startswith(("api/", "assets/", "bot/", "auth/")):
        raise HTTPException(status_code=404)
    return FileResponse(FRONTEND_DIST / "index.html")
