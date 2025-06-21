import aiohttp
from typing import Optional
from .settings import settings

_session: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(base_url=str(settings.API_URL))
    return _session


async def api_get(path: str) -> dict:
    session = await _get_session()
    async with session.get(path) as response:
        response.raise_for_status()
        if "application/json" in response.headers.get("Content-Type", ""):
            return await response.json()
        else:
            text = await response.text()
            raise ValueError(f"Expected JSON, got: {text[:200]}")


async def api_post(path: str, data: Optional[dict] = None) -> dict:
    session = await _get_session()
    async with session.post(path, json=data) as response:
        response.raise_for_status()
        return await response.json()


async def close():
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None
