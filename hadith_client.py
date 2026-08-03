import aiohttp
from typing import Optional, Dict, Any
from config import CONFIG
from logger import LOGGER

class HadithAPIClient:
    BASE_URL = "https://hadithapi.com/api/hadiths"

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        # Masukkan HADITH_API_KEY ke Config atau st.secrets
        self.api_key = getattr(CONFIG, "HADITH_API_KEY", "")

    async def search_hadith(self, query: str, book: Optional[str] = None) -> str:
        """Cari hadits berdasarkan kata kunci/topik dari HadithAPI."""
        if not self.api_key:
            LOGGER.warning("HADITH_API_KEY belum dikonfigurasi.")
            return ""

        params = {
            "apiKey": self.api_key,
            "paginate": 3  # Ambil 3 hadits teratas
        }
        
        if book:
            params["book"] = book  # contoh: 'sahih-bukhari', 'sahih-muslim', dll.
        else:
            params["search"] = query

        try:
            async with self.session.get(self.BASE_URL, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    hadiths = data.get("hadiths", {}).get("data", [])
                    if not hadiths:
                        return "[HADITH API: Tidak ditemukan hadits yang cocok.]"

                    formatted_results = []
                    for h in hadiths:
                        book_name = h.get("book", {}).get("bookName", "Hadith")
                        hadith_num = h.get("hadithNumber", "")
                        heading = h.get("headingEnglish", "") or h.get("headingIndonesian", "")
                        matan_ar = h.get("hadithArabic", "")
                        trans_en = h.get("hadithEnglish", "")

                        item = (
                            f"📖 Source: {book_name} No. {hadith_num}\n"
                            f"📌 Bab/Heading: {heading}\n"
                            f"🇸🇦 Matan Arab: {matan_ar}\n"
                            f"🌐 Translation: {trans_en}"
                        )
                        formatted_results.append(item)

                    return "[VERIFIED HADITH DATA INJECTED FROM HADITHAPI.COM]\n\n" + "\n\n---\n\n".join(formatted_results)
                else:
                    LOGGER.warning(f"HadithAPI response status: {resp.status}")
                    return ""
        except Exception as e:
            LOGGER.error(f"Error fetching from HadithAPI: {e}")
            return ""
