import asyncio
import logging
from importlib import reload
from types import ModuleType
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

import aiohttp

from .settings import settings
from .client import api_get

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("tg_bot")

bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None
current_token: Optional[str] = None


def fresh_router() -> "ModuleType.router":
    from . import handlers
    reload(handlers)
    return handlers.router


async def switch_bot(token: Optional[str]) -> None:
    global bot, dp, current_token

    if token == current_token:
        return

    if bot:
        log.info("Stopping previous bot session")
        try:
            await dp.stop_polling()
        except RuntimeError:
            pass
        await bot.session.close()
        bot = dp = None

    if token:
        log.info("Starting bot polling")
        try:
            new_bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
            new_dp = Dispatcher()
            new_dp.include_router(fresh_router())
            bot, dp = new_bot, new_dp
            asyncio.create_task(new_dp.start_polling(new_bot))
        except Exception as e:
            log.error(f"Cannot start bot: {e}")
            bot = dp = None
    else:
        log.warning("BOT_TOKEN is empty — bot disabled")

    current_token = token or None
    settings.BOT_TOKEN = token or ""


async def wait_for_api(url: str, retries: int = 10, delay: int = 2):
    """Ждет, пока API станет доступен"""
    for i in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        log.info("API доступен — продолжаем")
                        return
        except Exception:
            pass
        log.warning(f"[{i}/{retries}] API недоступен — жду {delay}с...")
        await asyncio.sleep(delay)
    raise RuntimeError("API не ответил после нескольких попыток")


async def reload_config() -> None:
    try:
        await wait_for_api(f"{settings.API_URL}/healthz")

        cfg = await api_get("/bot/config")
        st = await api_get("/bot/settings")
        settings.ADMIN_IDS = (cfg.get("admin_ids") or "").strip()

        if not st.get("bot_enabled", False):
            log.info("BOT_ENABLED = False — выключаю бота")
            await switch_bot(None)
            return

        await switch_bot(cfg.get("bot_token"))
    except Exception as e:
        log.error(f"Failed to reload config: {e}")


async def main() -> None:
    await reload_config()

    from .db_listener import ConfigWatcher
    watcher = ConfigWatcher(settings.DB_DSN, reload_config)
    await watcher.start()

    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot остановлен пользователем")
