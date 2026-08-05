import json
import aiohttp
from typing import Optional
from config import CONFIG
from logger import LOGGER

class IslamicAPIClient:
    """Universal Client - Force English data fetch for maximum stability"""
    BASE_URL = "https://islamicapi.com/api/v1"

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_key = getattr(CONFIG, "ISLAMIC_API_KEY", "").strip()

    def _get_headers(self):
        headers = {"User-Agent": "IslamicAIBot/1.0"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _geocode_city(self, city: str):
        url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1"
        headers = {"User-Agent": "IslamicAIBot/1.0"}
        try:
            async with self.session.get(url, headers=headers, timeout=8) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        return data[0]['lat'], data[0]['lon']
        except Exception as e:
            LOGGER.error(f"Geocoding error for city {city}: {e}")
        return None, None

    async def get_prayer_times(self, city: str) -> str:
        lat, lon = await self._geocode_city(city)
        if not lat:
            return f"[ERROR: Coordinate for city '{city}' not found.]"
        
        params = {"lat": lat, "lon": lon, "method": 3, "school": 1}
        if self.api_key: params["api_key"] = self.api_key
        
        try:
            async with self.session.get(f"{self.BASE_URL}/prayer-time/", params=params, headers=self._get_headers(), timeout=8) as r:
                if r.status == 200: return await r.text()
                return f"[INFO: Fetch prayer times for '{city}' from internal knowledge.]"
        except Exception:
            return f"[INFO: Fetch prayer times for '{city}' from internal knowledge.]"

    async def get_fasting_time(self, city: str) -> str:
        lat, lon = await self._geocode_city(city)
        if not lat:
            return f"[ERROR: Coordinate for city '{city}' not found.]"
            
        params = {"lat": lat, "lon": lon, "method": 3}
        if self.api_key: params["api_key"] = self.api_key
        
        try:
            async with self.session.get(f"{self.BASE_URL}/fasting/", params=params, headers=self._get_headers(), timeout=8) as r:
                if r.status == 200: return await r.text()
                return f"[INFO: Fetch fasting schedule for '{city}' from internal knowledge.]"
        except Exception:
            return f"[INFO: Fetch fasting schedule for '{city}' from internal knowledge.]"

    async def get_zakat_nisab(self, currency: str) -> str:
        clean_curr = currency[:3].lower()
        params = {"standard": "classical", "currency": clean_curr, "unit": "g"}
        if self.api_key: params["api_key"] = self.api_key
        
        try:
            async with self.session.get(f"{self.BASE_URL}/zakat-nisab/", params=params, headers=self._get_headers(), timeout=8) as r:
                if r.status == 200: return await r.text()
                return f"[INFO: Calculate Zakat Nisab for '{clean_curr.upper()}' using 85g gold / 595g silver standard.]"
        except Exception:
            return f"[INFO: Calculate Zakat Nisab for '{clean_curr.upper()}' using 85g gold / 595g silver standard.]"

    async def get_asmaul_husna(self, lang_code: str, name_query: str) -> str:
        # HARDCODE: Selalu minta data 'en' ke API
        params = {"language": "en"}
        if self.api_key: params["api_key"] = self.api_key
        
        try:
            async with self.session.get(f"{self.BASE_URL}/asma-ul-husna/", params=params, headers=self._get_headers(), timeout=8) as r:
                if r.status == 200:
                    data = await r.json()
                    names = data.get("data", {}).get("names", [])
                    matched = [n for n in names if name_query.lower() in n.get("transliteration", "").lower() or name_query.lower() in n.get("translation", "").lower()]
                    return json.dumps(matched if matched else names[:3], indent=2)
                return f"[INFO: Explain Asmaul Husna '{name_query}' in target language.]"
        except Exception:
            return f"[INFO: Explain Asmaul Husna '{name_query}'.]"

    async def get_dua(self, lang_code: str) -> str:
        # HARDCODE: Selalu minta data 'en' ke API
        params = {"type": "translation", "lang": "en", "random": "true"}
        if self.api_key: params["api_key"] = self.api_key
        
        try:
            async with self.session.get(f"{self.BASE_URL}/dua/", params=params, headers=self._get_headers(), timeout=8) as r:
                if r.status == 200: return await r.text()
                return "[INFO: Provide authentic Duas directly from Quran and Sunnah.]"
        except Exception:
            return "[INFO: Provide authentic Duas directly from Quran and Sunnah.]"

    async def get_ruqyah(self, lang_code: str) -> str:
        # HARDCODE: Selalu minta data 'en' ke API
        params = {"type": "instant", "lang": "en", "program": "brief-ruqya", "source": "from-quran", "random": "true"}
        if self.api_key: params["api_key"] = self.api_key
        
        try:
            async with self.session.get(f"{self.BASE_URL}/ruqyah/", params=params, headers=self._get_headers(), timeout=8) as r:
                if r.status == 200: return await r.text()
                return "[INFO: Provide Ruqyah verses from Quran and authentic Sunnah.]"
        except Exception:
            return "[INFO: Provide Ruqyah guidance.]"
