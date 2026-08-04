import json
import aiohttp
from typing import Optional
from config import CONFIG
from logger import LOGGER

class IslamicAPIClient:
    """Universal Client untuk semua fitur di islamicapi.com"""
    # Base URL utama API, pastikan sesuai dengan dokumentasi di foto
    BASE_URL = "https://islamicapi.com/api" 

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_key = getattr(CONFIG, "ISLAMIC_API_KEY", "")

    async def _fetch_and_dump(self, endpoint: str, params: dict) -> str:
        """Fungsi helper dinamis untuk mengambil data API dan menjadikannya teks JSON"""
        if self.api_key:
            params["apiKey"] = self.api_key

        try:
            async with self.session.get(f"{self.BASE_URL}/{endpoint}", params=params, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Coba ambil isi "data" (struktur paling umum di REST API)
                    items = data.get("data", data) 
                    if not items:
                        return f"[API KOSONG: Tidak ada data ditemukan untuk pencarian ini di /{endpoint}]"

                    # Batasi jumlah array agar token AI Groq tidak jebol (maksimal 3 data teratas)
                    if isinstance(items, list):
                        items = items[:3] 
                    
                    # Ubah jadi string JSON rapi agar LLM Groq bisa membacanya dengan akurat
                    raw_text = json.dumps(items, indent=2, ensure_ascii=False)
                    return f"[VERIFIED RAW DATA DARI ISLAMICAPI.COM (/{endpoint})]\n\n{raw_text}"
                else:
                    LOGGER.warning(f"IslamicAPI [{endpoint}] response HTTP {resp.status}")
                    return "[Error: Gagal terhubung ke server API islamicapi.com]"
        except Exception as e:
            LOGGER.error(f"Exception di IslamicAPI [{endpoint}]: {e}")
            return f"[Error Exception: {e}]"

    # ==========================================
    # Endpoint Commands (sesuaikan nama endpoint)
    # ==========================================
    async def get_dua(self, topic: str) -> str:
        return await self._fetch_and_dump("dua", {"search": topic})

    async def get_asmaul_husna(self, nama: str) -> str:
        return await self._fetch_and_dump("asmaulhusna", {"search": nama})
        
    async def get_kisah_nabi(self, nabi: str) -> str:
        return await self._fetch_and_dump("kisahnabi", {"search": nabi})
        
    async def get_jadwal_shalat(self, kota: str) -> str:
        # Jadwal shalat biasanya memakai parameter kota (city)
        return await self._fetch_and_dump("shalat", {"city": kota})
