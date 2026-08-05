import json
import aiohttp
from typing import Optional
from config import CONFIG
from logger import LOGGER

class IslamicAPIClient:
    """Universal Client matching official islamicapi.com/api/v1 documentation"""
    BASE_URL = "https://islamicapi.com/api/v1"

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_key = getattr(CONFIG, "ISLAMIC_API_KEY", "")

    async def _geocode_city(self, city: str):
        """Mengubah nama kota menjadi Latitude & Longitude via OpenStreetMap"""
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
            return f"[ERROR: Koordinat untuk kota '{city}' tidak ditemukan.]"
        
        params = {"lat": lat, "lon": lon, "method": 3, "school": 1}
        if self.api_key: 
            params["api_key"] = self.api_key
        
        async with self.session.get(f"{self.BASE_URL}/prayer-time/", params=params) as r:
            return await r.text()

    async def get_fasting_time(self, city: str) -> str:
        lat, lon = await self._geocode_city(city)
        if not lat:
            return f"[ERROR: Koordinat untuk kota '{city}' tidak ditemukan.]"
            
        params = {"lat": lat, "lon": lon, "method": 3}
        if self.api_key: 
            params["api_key"] = self.api_key
        
        async with self.session.get(f"{self.BASE_URL}/fasting/", params=params) as r:
            return await r.text()

    async def get_zakat_nisab(self, currency: str) -> str:
        # Currency ISO code (usd, idr, gbp, dll)
        params = {"standard": "classical", "currency": currency[:3].lower(), "unit": "g"}
        if self.api_key: 
            params["api_key"] = self.api_key
        
        async with self.session.get(f"{self.BASE_URL}/zakat-nisab/", params=params) as r:
            return await r.text()

    async def get_asmaul_husna(self, lang_code: str, name_query: str) -> str:
        params = {"language": lang_code[:2].lower()}
        if self.api_key: 
            params["api_key"] = self.api_key
        
        async with self.session.get(f"{self.BASE_URL}/asma-ul-husna/", params=params) as r:
            if r.status == 200:
                data = await r.json()
                names = data.get("data", {}).get("names", [])
                # Filter 99 nama hanya ke nama yang dicari user
                matched = [n for n in names if name_query.lower() in n.get("transliteration", "").lower() or name_query.lower() in n.get("translation", "").lower()]
                return json.dumps(matched if matched else names[:3], indent=2)
            return await r.text()

    async def get_dua(self, lang_code: str) -> str:
        # Mengambil random doa 
        params = {"type": "translation", "lang": lang_code[:2].lower(), "random": "true"}
        if self.api_key: 
            params["api_key"] = self.api_key
        
        async with self.session.get(f"{self.BASE_URL}/dua/", params=params) as r:
            return await r.text()

    async def get_ruqyah(self, lang_code: str) -> str:
        # Mengambil random ruqyah
        params = {"type": "instant", "lang": lang_code[:2].lower(), "program": "brief-ruqya", "source": "from-quran", "random": "true"}
        if self.api_key: 
            params["api_key"] = self.api_key
        
        async with self.session.get(f"{self.BASE_URL}/ruqyah/", params=params) as r:
            return await r.text()
