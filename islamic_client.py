import json
import aiohttp
from typing import Optional
from config import CONFIG
from logger import LOGGER

class IslamicAPIClient:
    """Universal Client for official endpoints in islamicapi.com"""
    BASE_URL = "https://islamicapi.com/api"

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_key = getattr(CONFIG, "ISLAMIC_API_KEY", "")

    async def _fetch_and_dump(self, endpoint: str, params: dict) -> str:
        if self.api_key:
            params["apiKey"] = self.api_key

        try:
            async with self.session.get(f"{self.BASE_URL}/{endpoint}", params=params, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("data", data) 
                    if not items:
                        return f"[EMPTY API: No data found for this search in /{endpoint}]"

                    if isinstance(items, list):
                        items = items[:3] 
                    
                    raw_text = json.dumps(items, indent=2, ensure_ascii=False)
                    return f"[VERIFIED RAW DATA FROM ISLAMICAPI.COM (/{endpoint})]\n\n{raw_text}"
                else:
                    LOGGER.warning(f"IslamicAPI [{endpoint}] HTTP response: {resp.status}")
                    return "[Error: Failed to connect to islamicapi.com server]"
        except Exception as e:
            LOGGER.error(f"Exception in IslamicAPI [{endpoint}]: {e}")
            return f"[Error Exception: {e}]"

    async def get_dua(self, topic: str) -> str:
        return await self._fetch_and_dump("dua", {"search": topic})

    async def get_asmaul_husna(self, name: str) -> str:
        return await self._fetch_and_dump("asmaulhusna", {"search": name})
        
    async def get_prayer_times(self, city: str) -> str:
        return await self._fetch_and_dump("prayertime", {"city": city})
        
    async def get_fasting_time(self, city: str) -> str:
        return await self._fetch_and_dump("fastingtime", {"city": city})

    async def get_zakat_nisab(self, asset_value: str) -> str:
        return await self._fetch_and_dump("zakatnisab", {"value": asset_value})

    async def get_ruqyah(self, ailment: str) -> str:
        return await self._fetch_and_dump("ruqyah", {"search": ailment})
