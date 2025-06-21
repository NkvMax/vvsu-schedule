from typing import Union
import asyncio, logging, asyncpg
from .settings import settings
from .client import api_get

log = logging.getLogger(__name__)


class ConfigWatcher:
    def __init__(self, dsn: str, on_change):
        self._dsn = dsn
        self._on_change = on_change  # coroutine
        self._conn: Union[asyncpg.Connection, None] = None

    async def start(self):
        self._conn = await asyncpg.connect(self._dsn)
        await self._conn.add_listener("bot_config", self._callback)
        log.info("LISTEN bot_config registered")

    async def _callback(self, *args):
        log.info("Got NOTIFY bot_config")
        await self._on_change()

    async def close(self):
        if self._conn:
            await self._conn.close()
