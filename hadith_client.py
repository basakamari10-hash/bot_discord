import aiohttp
from typing import Optional, Dict, Any
from config import CONFIG
from logger import LOGGER

class HadithClient:
    BASE_URL = "https://hadithapi.com/api/hadiths"

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_key = getattr(CONFIG, "HADITH_API_KEY", "")

    async def search_hadiths(self, topic: str, book: Optional[str] = None, language: Optional[str] = None) -> str:
        """Cari hadits dari HadithAPI dinamis berdasarkan bahasa user."""
        if not self.api_key:
            LOGGER.warning("HADITH_API_KEY belum dikonfigurasi.")
            return ""

        # Standarisasi input bahasa
        lang_lower = str(language).lower() if language else "en"

        if lang_lower in ["id", "indonesian", "indonesia", "indo"]:
            search_key = "hadithIndonesian"
            trans_key = "hadithIndonesian"
            heading_key = "headingIndonesian"
        elif lang_lower in ["ur", "urdu"]:
            search_key = "hadithUrdu"
            trans_key = "hadithUrdu"
            heading_key = "headingUrdu"
        elif lang_lower in ["ar", "arabic", "arab"]:
            search_key = "hadithArabic"
            trans_key = "hadithArabic"
            heading_key = "headingArabic"
        else:
            search_key = "hadithEnglish"
            trans_key = "hadithEnglish"
            heading_key = "headingEnglish"

        params = {
            "apiKey": self.api_key,
            "paginate": 3,
            search_key: topic
        }
        
        if book:
            params["book"] = book 

        try:
            async with self.session.get(self.BASE_URL, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    hadiths = data.get("hadiths", {}).get("data", [])
                    
                    if not hadiths:
                        return f"[HADITH API: Tidak ditemukan hadits dengan topik '{topic}' di buku '{book or 'Semua Buku'}'.]"

                    formatted_results = []
                    for h in hadiths:
                        book_name = h.get("book", {}).get("bookName", "Hadith")
                        hadith_num = h.get("hadithNumber", "")
                        heading = h.get(heading_key) or h.get("headingEnglish") or h.get("headingArabic", "No Chapter")
                        matan_ar = h.get("hadithArabic", "")
                        trans_text = h.get(trans_key) or h.get("hadithEnglish", "")

                        item = (
                            f"📖 Source: {book_name} No. {hadith_num}\n"
                            f"📌 Chapter/Bab: {heading}\n"
                            f"🇸🇦 Arabic: {matan_ar}\n"
                            f"🌐 Translation: {trans_text}"
                        )
                        formatted_results.append(item)

                    return "[VERIFIED HADITH DATA INJECTED FROM HADITHAPI.COM]\n\n" + "\n\n---\n\n".join(formatted_results)
                else:
                    LOGGER.warning(f"HadithAPI response status: {resp.status}")
                    return ""
        except Exception as e:
            LOGGER.error(f"Error fetching from HadithAPI: {e}")
            return ""
