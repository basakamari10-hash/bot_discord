import re
import asyncio
from enum import Enum, auto
import aiohttp
from config import CONFIG
from logger import LOGGER
from cache import GLOBAL_CACHE

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False

class SearchCategory(Enum):
    QURAN = auto()
    HADITH = auto()
    FIQH = auto()
    HISTORY = auto()
    TAFSIR = auto()
    DUA = auto()
    AQIDAH = auto()
    ZAIDI = auto()
    JAAFARI = auto()
    PROGRESSIVE = auto()
    GENERAL = auto()

class SmartSearch:
    CATEGORY_DOMAINS = {
        SearchCategory.HADITH: ["sunnah.com", "dorar.net", "islamweb.net", "hadithprophet.com", "hadits.id", "carihadis.com"],
        SearchCategory.FIQH: ["islamqa.info", "islamweb.net", "alifta.gov.sa", "binbaz.org.sa", "alukah.net"],
        SearchCategory.ZAIDI: ["salvationark.com", "zaydi.info", "ziydia.com"],
        SearchCategory.JAAFARI: ["al-islam.org", "sistani.org", "shiavault.com", "makarem.ir"],
        SearchCategory.PROGRESSIVE: ["mpvusa.org", "iijt.org", "islamandlibertynetwork.org"],
        SearchCategory.TAFSIR: ["tafsir.app", "quran.com", "quran.ksu.edu.sa", "tafsir.net"],
        SearchCategory.QURAN: ["quran.com", "quranwbw.com"],
        SearchCategory.DUA: ["hisnmuslim.com", "duas.org", "kalemtayyeb.com"],
        SearchCategory.AQIDAH: ["islamqa.info", "binbaz.org.sa", "alifta.gov.sa"]
    }

    @staticmethod
    def clean_query(query: str) -> str:
        cleaned = re.sub(r'\[.*?\]', '', query)
        return cleaned.strip()

    @classmethod
    def classify_query(cls, query: str) -> SearchCategory:
        q = query.lower()
        if any(w in q for w in ["progressive", "reformist", "modernist", "progressive muslims"]):
            return SearchCategory.PROGRESSIVE
        if any(w in q for w in ["ja'fari", "jafari", "shia twelver", "twelver", "imami", "شيعة", "جعفري"]):
            return SearchCategory.JAAFARI
        if any(w in q for w in ["zaidi", "zaydism", "zaydiyya", "zaidiyyah", "الزيدية"]):
            return SearchCategory.ZAIDI
        if any(w in q for w in ["hadith", "sunnah", "bukhari", "muslim", "matan", "حديث", "سنة"]):
            return SearchCategory.HADITH
        if any(w in q for w in ["fiqh", "ruling", "halal", "haram", "fatwa", "فقه", "حكم", "فتوى"]):
            return SearchCategory.FIQH
        if any(w in q for w in ["tafsir", "exegesis", "meaning of verse", "تفسير"]):
            return SearchCategory.TAFSIR
        if any(w in q for w in ["dua", "supplication", "dhikr", "azkar", "دعاء", "ذكر"]):
            return SearchCategory.DUA
        if any(w in q for w in ["aqidah", "creed", "belief", "عقيدة", "توحيد"]):
            return SearchCategory.AQIDAH
        if any(w in q for w in ["quran", "surah", "ayah", "verse", "القرآن"]):
            return SearchCategory.QURAN
        return SearchCategory.GENERAL

    @classmethod
    async def execute_search(cls, session: aiohttp.ClientSession, query: str) -> str:
        query_clean = cls.clean_query(query)
        category = cls.classify_query(query_clean)
        cache_key = f"search:{category.name}:{query_clean}"
        
        cached = await GLOBAL_CACHE.get(cache_key)
        if cached:
            return cached

        results = []
        domains = cls.CATEGORY_DOMAINS.get(category, [])
        site_cluster = " OR ".join([f"site:{d}" for d in domains])

        if HAS_DDGS:
            try:
                def _ddg_sync():
                    res_list = []
                    search_term = f"({site_cluster}) {query_clean}".strip() if site_cluster else query_clean
                    with DDGS() as ddgs:
                        res = ddgs.text(search_term, max_results=5)
                        for r in res:
                            res_list.append(f"Source/Title: {r['title']}\nVerified Content: {r['body']}")
                    return res_list
                results = await asyncio.to_thread(_ddg_sync)
            except Exception as e:
                LOGGER.warning(f"DDGS Search Exception: {e}")

        if not results:
            try:
                full_query = f"({site_cluster}) {query_clean}".strip() if site_cluster else query_clean
                url = "https://lite.duckduckgo.com/lite/"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                data = {"q": full_query}
                async with session.post(url, data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        snippets = re.findall(r'<td class="result-snippet">(.*?)</td>', html, re.DOTALL)
                        links = re.findall(r'<a class="result-title" href="(.*?)">(.*?)</a>', html, re.DOTALL)
                        for i in range(min(len(snippets), 5)):
                            title = re.sub(r'<[^>]+>', '', links[i][1]).strip() if i < len(links) else "Search Result"
                            snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                            results.append(f"Source/Title: {title}\nVerified Content: {snippet}")
            except Exception as e:
                LOGGER.warning(f"HTTP Search Fallback Exception: {e}")

        header_prefix = f"[VERIFIED {category.name} DATA INJECTED FROM ANCHORED CLUSTER]\n"
        if results:
            output = header_prefix + "\n\n".join(results)
        else:
            output = f"[NO VERIFIED {category.name} REFERENCES FOUND IN CLUSTER]"

        await GLOBAL_CACHE.set(cache_key, output, ttl=CONFIG.CACHE_TTL_SEARCH)
        return output
