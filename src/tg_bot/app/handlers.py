from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    BotCommand,
    FSInputFile,
)
from pathlib import Path
from .client import api_get, api_post
from .settings import settings
import asyncio
import logging
from datetime import datetime
import pytz

router = Router()
logger = logging.getLogger("handlers")

AVATAR_PATH = Path(__file__).parent / "avatar" / "avatar.jpeg"


def parse_admin_ids():
    ids = getattr(settings, "ADMIN_IDS", "")
    if isinstance(ids, str):
        return set(int(i) for i in ids.replace(" ", "").split(",") if i)
    elif isinstance(ids, (list, set)):
        return set(int(i) for i in ids)
    return set()


def is_admin(user_id: int) -> bool:
    admins = parse_admin_ids()
    logger.info(f"Admins: {admins} | user: {user_id}")
    return user_id in admins


def kb_main():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Синхронизация", callback_data="sync_now"),
                InlineKeyboardButton(text="📊 Статус", callback_data="status"),
            ]
        ]
    )


def status_lines(runs: list[dict]) -> str:
    emoji = {"done": "✅", "success": "✅", "pending": "⚠️", "error": "❌"}
    return "\n".join(
        f"{emoji.get(r['status'], '❔')} <b>{r['time']}</b> — {r['detail'] or r['status']}"
        for r in runs
    )


def greeting_by_time() -> str:
    tz = pytz.timezone("Asia/Vladivostok")
    now = datetime.now(tz)
    hour = now.hour

    if 5 <= hour < 12:
        return "Доброе утро"
    elif 12 <= hour < 17:
        return "Добрый день"
    elif 17 <= hour < 23:
        return "Добрый вечер"
    else:
        return "Доброй ночи"


@router.message(CommandStart())
async def cmd_start(m: Message):
    from_user = m.from_user
    if not is_admin(from_user.id):
        await m.answer("У вас нет доступа к этому боту.")
        return

    greeting = greeting_by_time()
    await m.answer(
        f"{greeting}, {from_user.first_name}!\n\n"
        "Чтобы бот выглядел красиво, установите аватарку через команду /set_pic.\n",
        reply_markup=kb_main()
    )

    await m.bot.set_my_commands([
        types.BotCommand(command="set_pic", description="Получить аватарку для BotFather"),
    ])


@router.message(Command("status"))
async def cmd_status(m: Message):
    logger.info(f"/status from {m.from_user.id}")
    if not is_admin(m.from_user.id):
        await m.answer("У вас нет доступа.")
        return
    await send_status(m)


@router.callback_query(F.data == "status")
async def cb_status(cb: CallbackQuery):
    logger.info(f"callback status from {cb.from_user.id}")
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await send_status(cb.message)
    await cb.answer()


async def send_status(target: Message):
    data = await api_get("/api/scheduler/overview")
    runs = (data.get("runs") or [])[:10]
    text = status_lines(runs) if runs else "История пуста."
    await target.answer(text, parse_mode="HTML", reply_markup=kb_main())


@router.message(Command("sync_now"))
async def cmd_sync(m: Message):
    logger.info(f"/sync_now from {m.from_user.id}")
    if not is_admin(m.from_user.id):
        await m.answer("Нет доступа.")
        return
    await launch_sync(m)


@router.callback_query(F.data == "sync_now")
async def cb_sync(cb: CallbackQuery):
    logger.info(f"callback sync_now from {cb.from_user.id}")
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    await launch_sync(cb.message)
    await cb.answer("Синхронизация запущена!")


async def launch_sync(target: Message):
    msg = await target.answer("🔄 Синхронизация запущена…")
    try:
        await api_post("/api/sync")
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка запуска: {e}", reply_markup=kb_main())
        return

    await asyncio.sleep(6)
    data = await api_get("/api/scheduler/overview")
    runs = (data.get("runs") or [])[:2]

    if runs:
        lines = status_lines(runs)
        await msg.edit_text(f"🔄 Синхронизация запущена…\n{lines}", parse_mode="HTML")
        await asyncio.sleep(3)

    last = runs[0] if runs else None
    if last and last["status"] in {"done", "success"}:
        await msg.edit_text("✅ Календарь синхронизирован!", reply_markup=kb_main())
    else:
        detail = last["detail"] if last else "Не удалось получить расписание."
        await msg.edit_text(f"❌ {detail}", reply_markup=kb_main())


@router.message(Command("set_pic"))
async def cmd_set_pic(m: Message):
    logger.info(f"/set_pic from {m.from_user.id}")
    if not is_admin(m.from_user.id):
        await m.answer("Нет доступа к аватарке.")
        return
    if not AVATAR_PATH.exists():
        await m.answer("Аватарка не найдена.")
        return
    await m.answer_photo(FSInputFile(str(AVATAR_PATH)))
    await m.answer(
        "⬆️ Скачайте картинку\n"
        "и отправьте ее в BotFather из галереи как фото.\n\n"
        "Важно: не пересылайте фото от бота — BotFather такое не принимает."
    )
