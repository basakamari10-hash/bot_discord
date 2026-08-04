import aiohttp
from typing import Optional
from config import CONFIG
from logger import LOGGER

class DuaAPIClient:
    # URL default untuk mencari doa (sesuaikan jika di dokumentasi islamicapi berbeda)
    BASE_URL = "https://islamicapi.com/api/v1/dua" 

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        # Mengambil ISLAMIC_API_KEY dari env/config (jika ada)
        self.api_key = getattr(CONFIG, "ISLAMIC_API_KEY", "") 

    async def search_dua(self, topic: str, language: str = "id") -> str:
        """
        Mencari data doa berdasarkan topik dari islamicapi.com
        """
        params = {
            "search": topic,
            "lang": language
        }
        
        if self.api_key:
            params["apiKey"] = self.api_key

        try:
            async with self.session.get(self.BASE_URL, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Mengambil array data doa (sesuaikan key "data" jika beda di dokumentasi)
                    duas = data.get("data", [])
                    if not duas:
                        return f"[DUA API: Tidak ditemukan doa spesifik untuk topik '{topic}'.]"

                    formatted_results = []
                    # Ambil maksimal 3 doa agar token tidak terlalu berat
                    for d in duas[:3]:
                        title = d.get("title", "Doa Pilihan")
                        arabic = d.get("arabic", "")
                        translation = d.get("translation", "")
                        reference = d.get("reference", "Sumber Umum")

                        item = (
                            f"📌 Topik/Judul: {title}\n"
                            f"🇸🇦 Teks Arab: {arabic}\n"
                            f"🌐 Arti: {translation}\n"
                            f"📚 Referensi: {reference}"
                        )
                        formatted_results.append(item)

                    return "[VERIFIED DUA DATA INJECTED FROM ISLAMICAPI.COM]\n\n" + "\n\n---\n\n".join(formatted_results)
                else:
                    LOGGER.warning(f"IslamicAPI response status: {resp.status}")
                    return "[Error: Gagal terhubung ke server IslamicAPI.]"
        except Exception as e:
            LOGGER.error(f"Error fetching from IslamicAPI: {e}")
            return f"[Error Exception: {e}]"
