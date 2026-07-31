# ==============================================================================
# bot_quran.py - Production-Ready Islamic & Quran Discord AI Bot (PART 1)
# ==============================================================================

#region Imports
import os
import sys
import re
import json
import time
import logging
import asyncio
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Union

import aiohttp
from aiohttp import web
import discord
from discord import app_commands
from discord.ext import commands, tasks

# Streamlit compatibility import
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    st = None
    HAS_STREAMLIT = False

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
#endregion

#region Configuration
def _get_secret(key: str, default: str = "") -> str:
    """Helper to fetch config secrets from Streamlit secrets or OS environment variables."""
    if HAS_STREAMLIT and hasattr(st, "secrets"):
        try:
            val = st.secrets.get(f"{key}_QURAN") or st.secrets.get(key)
            if val:
                return str(val)
        except Exception:
            pass
    return os.getenv(f"{key}_QURAN") or os.getenv(key) or default

@dataclass
class Config:
    """Central configuration management."""
    DISCORD_TOKEN: str = field(default_factory=lambda: _get_secret("DISCORD_TOKEN"))
    GROQ_API_KEY: str = field(default_factory=lambda: _get_secret("GROQ_API_KEY"))
    STREAMLIT_URL: str = field(default_factory=lambda: _get_secret("STREAMLIT_URL", "https://your-app-name.streamlit.app"))
    PORT: int = field(default_factory=lambda: int(os.getenv("PORT", "8080")))
    
    # 3-Model Routing Strategy (Groq)
    MODEL_HEAVY: str = "openai/gpt-oss-120b"          # Heavy Model (Tafsir & Fiqh)
    MODEL_LIGHT: str = "llama-3.3-70b-versatile"     # High-Intelligence Model
    MODEL_FALLBACK: str = "llama-3.1-8b-instant"     # Fallback
    
    # Model Fallback Priority List
    GROQ_MODELS: List[str] = field(default_factory=lambda: [
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-120b",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant"
    ])
    
    # Cache Expiration (Seconds)
    CACHE_TTL_GROQ: int = 86400    # 24 Hours
    CACHE_TTL_SEARCH: int = 43200  # 12 Hours
    
    # Rate Limits
    USER_COOLDOWN_SECONDS: float = 3.0
    CONCURRENT_REQUESTS_LIMIT: int = 5
    MAX_RETRIES: int = 3
    REQUEST_TIMEOUT: float = 25.0
    
    # Quran JSON Database Paths
    HAFS_JSON_PATH: str = os.getenv("HAFS_JSON_PATH", "qpc-hafs.json")
    ENGLISH_WBW_PATH: str = os.getenv("ENGLISH_WBW_PATH", "english-wbw-translation.json")

CONFIG = Config()
#endregion

#region Logger
def setup_logger() -> logging.Logger:
    """Configures structured logging."""
    logger = logging.getLogger("IslamicAI")
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(handler)
        
    return logger

LOGGER = setup_logger()
#endregion

#region Cache
class TTLCache:
    """Thread-safe and async-friendly in-memory TTL Cache."""
    def __init__(self, default_ttl: int = 3600):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                return None
            val, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            return val

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            expiration = time.time() + (ttl if ttl is not None else self._default_ttl)
            self._cache[key] = (value, expiration)

GLOBAL_CACHE = TTLCache(default_ttl=CONFIG.CACHE_TTL_GROQ)
#endregion

#region Rate Limiter
class RateLimiter:
    """Per-user cooldown and concurrent execution concurrency manager."""
    def __init__(self, cooldown: float = 3.0, max_concurrent: int = 5):
        self.cooldown = cooldown
        self.user_last_request: Dict[int, float] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, user_id: int) -> Tuple[bool, float]:
        async with self._lock:
            now = time.time()
            last = self.user_last_request.get(user_id, 0.0)
            elapsed = now - last
            if elapsed < self.cooldown:
                return True, self.cooldown - elapsed
            self.user_last_request[user_id] = now
            return False, 0.0

GLOBAL_RATE_LIMITER = RateLimiter(
    cooldown=CONFIG.USER_COOLDOWN_SECONDS,
    max_concurrent=CONFIG.CONCURRENT_REQUESTS_LIMIT
)
#endregion

#region Quran Database
class QuranDatabase:
    """
    Quran DB Engine supporting dual JSON files (qpc-hafs.json & english-wbw-translation.json).
    Supports format keys ("1:1"), array items, dict objects, and Word-By-Word (WBW) structures.
    """
    def __init__(self, arabic_path: str = CONFIG.HAFS_JSON_PATH, translation_path: str = CONFIG.ENGLISH_WBW_PATH):
        self.arabic_path = arabic_path
        self.translation_path = translation_path
        self.arabic_data: Dict[str, Dict[str, str]] = {}
        self.translation_data: Dict[str, Dict[str, str]] = {}
        self.is_loaded: bool = False

    def load_data(self) -> bool:
        """Loads Arabic and Translation JSON databases into RAM."""
        # 1. Load Arabic JSON
        if os.path.exists(self.arabic_path):
            try:
                with open(self.arabic_path, "r", encoding="utf-8") as f:
                    raw_ar = json.load(f)
                self.arabic_data = self._parse_json(raw_ar)
                LOGGER.info(f"Loaded Arabic Quran Data: {self.arabic_path}")
            except Exception as e:
                LOGGER.error(f"Failed to load Arabic file ({self.arabic_path}): {e}")
        else:
            LOGGER.warning(f"Arabic Quran file '{self.arabic_path}' not found!")

        # 2. Load Translation JSON
        if os.path.exists(self.translation_path):
            try:
                with open(self.translation_path, "r", encoding="utf-8") as f:
                    raw_tr = json.load(f)
                self.translation_data = self._parse_json(raw_tr)
                LOGGER.info(f"Loaded Translation Data: {self.translation_path}")
            except Exception as e:
                LOGGER.error(f"Failed to load Translation file ({self.translation_path}): {e}")
        else:
            LOGGER.warning(f"Translation file '{self.translation_path}' not found!")

        self.is_loaded = bool(self.arabic_data or self.translation_data)
        return self.is_loaded

    def _parse_json(self, raw_data: Any) -> Dict[str, Dict[str, str]]:
        """Parses verse_key ("1:1"), dictionary structures, array lists, and WBW structures."""
        parsed: Dict[str, Dict[str, str]] = {}

        if isinstance(raw_data, dict):
            for key, val in raw_data.items():
                surah = ""
                ayah = ""

                if ":" in key:
                    parts = key.split(":")
                    surah, ayah = parts[0], parts[1]
                elif isinstance(val, dict):
                    surah = str(val.get("surah") or val.get("surah_number") or val.get("chapter") or "")
                    ayah = str(val.get("ayah") or val.get("verse") or val.get("verse_number") or "")

                text_val = ""
                if isinstance(val, dict):
                    if "text" in val or "text_uthmani" in val:
                        t = val.get("text_uthmani") or val.get("text")
                        if isinstance(t, list):
                            text_val = " ".join([str(w.get("text", w) if isinstance(w, dict) else w) for w in t])
                        else:
                            text_val = str(t)
                    elif "translation" in val or "text_english" in val or "t" in val:
                        text_val = str(val.get("translation") or val.get("text_english") or val.get("t"))
                    elif "words" in val:
                        words = val["words"]
                        if isinstance(words, list):
                            text_val = " ".join([w.get("translation", w.get("text", "")) if isinstance(w, dict) else str(w) for w in words])
                    else:
                        text_val = str(val)
                else:
                    text_val = str(val)

                if surah and ayah:
                    if surah not in parsed:
                        parsed[surah] = {}
                    parsed[surah][ayah] = text_val.strip()

        elif isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict):
                    surah = str(item.get("surah") or item.get("surah_number") or item.get("chapter") or "")
                    ayah = str(item.get("ayah") or item.get("verse") or item.get("verse_number") or "")
                    text_val = item.get("text") or item.get("text_uthmani") or item.get("translation") or item.get("text_english") or item.get("t") or ""
                    
                    if surah and ayah:
                        if surah not in parsed:
                            parsed[surah] = {}
                        parsed[surah][ayah] = str(text_val).strip()

        return parsed

    def get_verse(self, surah_num: int, ayah_num: int) -> Optional[Dict[str, Any]]:
        """Retrieves exact Arabic text and reference translation from JSON RAM cache."""
        s_key = str(surah_num)
        a_key = str(ayah_num)
        
        ar_text = self.arabic_data.get(s_key, {}).get(a_key, "")
        tr_text = self.translation_data.get(s_key, {}).get(a_key, "")

        if ar_text or tr_text:
            return {
                "surah_name": f"Surah {surah_num}",
                "surah_num": surah_num,
                "ayah_num": ayah_num,
                "ar": ar_text,
                "tr": tr_text
            }
        return None

    def get_range(self, surah_num: int, start_ayah: int, end_ayah: int) -> List[Dict[str, Any]]:
        """Retrieves a range of verses."""
        results = []
        for a in range(start_ayah, end_ayah + 1):
            v = self.get_verse(surah_num, a)
            if v:
                results.append(v)
        return results

    @staticmethod
    def parse_verse_key(text: str) -> Optional[Tuple[int, int, Optional[int]]]:
        """Parses patterns like '2:255' or '1:1-7'."""
        match = re.search(r'\b(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\b', text)
        if match:
            surah = int(match.group(1))
            start_a = int(match.group(2))
            end_a = int(match.group(3)) if match.group(3) else None
            if 1 <= surah <= 114:
                return surah, start_a, end_a
        return None

QURAN_DB = QuranDatabase()
#endregion# ==============================================================================
# bot_quran.py - Production-Ready Islamic & Quran Discord AI Bot (PART 2)
# ==============================================================================

#region Search
class SearchCategory(Enum):
    QURAN = auto()
    HADITH = auto()
    FIQH = auto()
    HISTORY = auto()
    TAFSIR = auto()
    DUA = auto()
    AQIDAH = auto()
    ZAIDI = auto()
    GENERAL = auto()

class SmartSearch:
    """Smart web search execution with site filters and clean query sanitation."""

    CATEGORY_DOMAINS = {
        SearchCategory.HADITH: ["sunnah.com", "dorar.net"],
        SearchCategory.FIQH: ["islamqa.info", "islamweb.net", "alifta.gov.sa"],
        SearchCategory.ZAIDI: ["salvationark.com", "zaydi.info", "ziydia.com"],
        SearchCategory.TAFSIR: ["tafsir.app", "quran.com", "quran.ksu.edu.sa"],
        SearchCategory.QURAN: ["quran.com", "quranwbw.com"],
        SearchCategory.DUA: ["hisnmuslim.com", "duas.org"],
        SearchCategory.AQIDAH: ["islamqa.info", "binbaz.org.sa", "alifta.gov.sa"]
    }

    @staticmethod
    def clean_query(query: str) -> str:
        """Removes formatting tags for accurate search."""
        cleaned = re.sub(r'\[.*?\]', '', query)
        return cleaned.strip()

    @classmethod
    def classify_query(cls, query: str) -> SearchCategory:
        q = query.lower()
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
        """Executes live web search using async DDGS or DuckDuckGo HTTP fallback."""
        query_clean = cls.clean_query(query)
        category = cls.classify_query(query_clean)
        cache_key = f"search:{category.name}:{query_clean}"
        
        cached = await GLOBAL_CACHE.get(cache_key)
        if cached:
            return cached

        results = []

        # Attempt 1: duckduckgo_search library in async thread if available
        if HAS_DDGS:
            try:
                def _ddg_sync():
                    res_list = []
                    domains = cls.CATEGORY_DOMAINS.get(category, [])
                    site_filter = " OR ".join([f"site:{d}" for d in domains])
                    search_term = f"quran verse hadith authentic fiqh {query_clean} {site_filter}".strip()
                    
                    with DDGS() as ddgs:
                        res = ddgs.text(search_term, max_results=4)
                        for r in res:
                            res_list.append(f"Title: {r['title']}\nContent: {r['body']}")
                    return res_list

                results = await asyncio.to_thread(_ddg_sync)
            except Exception as e:
                LOGGER.warning(f"DDGS Search Exception: {e}")

        # Attempt 2: Direct HTTP search fallback via aiohttp
        if not results:
            try:
                domains = cls.CATEGORY_DOMAINS.get(category, [])
                site_filter = " OR ".join([f"site:{d}" for d in domains])
                full_query = f"{query_clean} {site_filter}".strip()
                url = f"https://lite.duckduckgo.com/lite/"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                data = {"q": full_query}

                async with session.post(url, data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        snippets = re.findall(r'<td class="result-snippet">(.*?)</td>', html, re.DOTALL)
                        links = re.findall(r'<a class="result-title" href="(.*?)">(.*?)</a>', html, re.DOTALL)

                        for i in range(min(len(snippets), 4)):
                            title = re.sub(r'<[^>]+>', '', links[i][1]).strip() if i < len(links) else "Search Result"
                            snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                            results.append(f"Title: {title}\nContent: {snippet}")
            except Exception as e:
                LOGGER.warning(f"HTTP Search Fallback Exception: {e}")

        output = "\n\n".join(results) if results else "NO VERIFIED WEB REFERENCES FOUND. Provide answer using general Qur'an/Hadith principles with Arabic text and cite general Fiqh book sources."
        await GLOBAL_CACHE.set(cache_key, output, ttl=CONFIG.CACHE_TTL_SEARCH)
        return output
#endregion

#region Groq Client
class GroqClient:
    """Async Groq Client with exponential backoff and multi-model failover."""
    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    @staticmethod
    def clean_repetition(text: str) -> str:
        """Removes repeated word patterns without clipping original sentences."""
        if not text:
            return ""
        pattern_word = r'(\b[\w\u0600-\u06FF\u0100-\u024F]+\b)(?:\s+\1){3,}'
        cleaned = re.sub(pattern_word, r'\1', text, flags=re.IGNORECASE)
        return cleaned.strip()

    async def chat_completion(
        self,
        prompt_text: str,
        system_prompt: str,
        preferred_model: str = CONFIG.MODEL_LIGHT
    ) -> str:
        if not CONFIG.GROQ_API_KEY:
            return "❌ Groq API key is not configured. Please set the GROQ_API_KEY or GROQ_API_KEY_QURAN environment variable."

        headers = {
            "Authorization": f"Bearer {CONFIG.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        # Build prioritized model fallback chain
        model_chain = [preferred_model]
        for m in [CONFIG.MODEL_HEAVY, CONFIG.MODEL_LIGHT, CONFIG.MODEL_FALLBACK]:
            if m not in model_chain:
                model_chain.append(m)

        for model_name in model_chain:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ],
                "temperature": 0.0,  # Pure Factual Grounding
                "max_tokens": 3000
            }

            for attempt in range(CONFIG.MAX_RETRIES):
                try:
                    async with self.session.post(
                        self.API_URL,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=CONFIG.REQUEST_TIMEOUT)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            raw_content = data['choices'][0]['message']['content']
                            return self.clean_repetition(raw_content)
                        elif resp.status in (429, 500, 502, 503, 504):
                            LOGGER.warning(f"Groq API HTTP {resp.status} on {model_name}, retrying (attempt {attempt + 1})...")
                            await asyncio.sleep((2 ** attempt) + 0.5)
                            continue
                        else:
                            LOGGER.warning(f"Groq API Error {resp.status}: {await resp.text()}")
                            break
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    LOGGER.warning(f"Groq Connection error ({e}) on model {model_name}, attempt {attempt + 1}")
                    await asyncio.sleep((2 ** attempt) + 0.5)

        return "⚠️ Sorry, all Groq AI servers are currently busy. Please try again in a few moments."
#endregion# ==============================================================================
# bot_quran.py - Production-Ready Islamic & Quran Discord AI Bot (PART 3)
# ==============================================================================

#region Prompt Builder
class PromptBuilder:
    """System Prompt Engine with Islamic Mandates and Context Injection."""
    
    SYSTEM_PROMPT = """
You are 'Islamic.AI', an authentic, highly respectful, and strictly factual AI assistant specialized in Islamic jurisprudence (Fiqh), Qur'an tafsir, authentic Hadiths, and Duas.

MANDATORY DALIL & CITATION RULES (STRICTLY ENFORCED FOR ALL COMMANDS & CHATS):

1. MANDATORY EVIDENCE (DALIL) & SOURCE CITATION IN EVERY RESPONSE:
   - EVERY SINGLE RESPONSE MUST INCLUDE:
     a) Clear Evidence / Dalil (Original Arabic text/Matan + Translation derived strictly from official reference data).
     b) Explicit Source Citation (e.g., "Surah Al-Baqarah: 183", "Sahih al-Bukhari No. 1", "Tafsir Ibn Kathir", "Kitab Al-Majmu' by Imam an-Nawawi", or "Kitab Fiqh al-Sunnah").
   - NEVER provide a plain opinion without grounding it in Qur'an/Hadith Dalil and recognized scholarly/kitāb sources.

2. STRICT TARGET LANGUAGE MANDATE (ZERO CONTEXT LEAKAGE & NO MIXING):
   - FULL RESPONSE TRANSLATION: You MUST write your ENTIRE response (explanations, Quran verse translations, Hadith matan/meaning translations, labels, citations, and disclaimer) strictly in the target language.
   - MANDATORY HADITH & QURAN TRANSLATION: Even if injected web search references or Quran context are in another language, you MUST fully translate all Hadith translations, Quran meanings, and labels into the user's target language (e.g., English, French, Arabic, German, Spanish, etc.).

3. QUR'ANIC ARABIC & TRANSLATION GROUNDING:
   - Whenever Quranic verses are cited, you MUST use the exact Arabic text provided in the prompt context from 'qpc-hafs.json'.
   - The translation MUST be derived directly from the injected reference JSON dataset, translated or adapted seamlessly to match the user's required target response language.

4. ZAYDI & COMPARATIVE MADHHAB REPOSITORIES & NEUTRALITY:
   - When queried about Zaydi Shīʿa jurisprudence (Fiqh) or history, prioritize authentic classical texts (such as Al-Majmu' al-Mu'tabar) and verified digital repositories such as salvationark.com, zaydi.info, and ziydia.com.
   - Maintain absolute academic objectivity and neutrality. Strictly avoid external polemical labels, sectarian insults, or ungrounded theological accusations. Present the school's mainstream jurisprudential positions strictly based on its recognized corpus.

5. ABSOLUTE ZERO FABRICATION (ANTI-HALLUCINATION):
   - ONLY cite specific Hadith numbers or verse numbers if grounded in authentic verified references.
   - FOR MODERN/CONTEMPORARY ISSUES: Do not invent fake literal Hadith narrations; cite general Qur'anic principles, Kaidah Fiqhiyyah, and Muamalah sources.

6. BIBLIOGRAPHIC ACCURACY & ANTI-FABRICATION RULE:
   - NEVER fabricate book volume numbers, page numbers, or specific edition details. 
   - If the exact volume or page number is not present in the verified search references, cite ONLY the general book name (e.g., "Tafsir al-Jalālayn" or "Tafsir Ibn Kathir") without inventing fake volume or page numbers.

7. CRITICAL QURAN PROHIBITION & HALLUCINATION GUARDRAIL:
   - NEVER WRITE OR GENERATE QURANIC ARABIC TEXT FROM MEMORY: You are strictly forbidden from generating Arabic Quranic text by yourself. Whenever official Quran data is provided in the prompt context, you MUST strictly use that exact text verbatim.

8. STRICT HADITH MATAN & QUOTATION GUARDRAIL (CRITICAL HADITH RULE):
   - NO FABRICATED HADITH QUOTES: Do NOT place Hadith matan inside quotation marks ("...") unless the exact, word-for-word text is explicitly provided in the verified web search references.
   - DIRECT QUOTE vs. GENERAL MEANING: If the exact verbatim Hadith matan is NOT present in the search reference, state the response as "General Meaning of Hadith" adapted strictly to your TARGET LANGUAGE. Translate the Hadith content fully into that target language.
   - STRICT HADITH NUMBERING: Never invent or guess Hadith numbers. If the search context does not verify the exact Hadith number, cite ONLY the collection name (e.g., "Sahih al-Bukhari, Book of Prophets").

9. MANDATORY DISCLAIMER:
   - Always end with a short reminder in the target response language to consult qualified Islamic scholars for official fatwas on complex or modern issues.
   - Also append: "NB: If you encounter AI hallucinations or problems with the AI bot, please contact @hanabihikari via DM with a screenshot."
"""

    @staticmethod
    def create_language_instruction(language_param: Optional[str]) -> str:
        """Enforces language translation mandates."""
        if language_param and language_param.strip():
            return (
                f"\n\n[STRICT TARGET LANGUAGE OVERRIDE - CRITICAL]\n"
                f"1. Target Language: FORCED to '{language_param.strip()}'.\n"
                f"2. Write EVERY SINGLE WORD of your response in '{language_param.strip()}'.\n"
                f"3. You MUST translate all Hadith translations/meanings, Quran translations, labels, and disclaimers into '{language_param.strip()}'."
            )
        else:
            return (
                "\n\n[STRICT AUTOMATIC LANGUAGE MATCHING - CRITICAL]\n"
                "1. Automatically detect the exact language used in the user's prompt/question above.\n"
                "2. Write EVERY SINGLE WORD of your response in that SAME detected language (e.g., English, French, Spanish, German, Arabic, etc.).\n"
                "3. MANDATORY TRANSLATION: Translate ALL Hadith text/meanings, Quran translations, labels, explanations, and disclaimers into the user's detected language."
            )

    @staticmethod
    def extract_quran_context(text: str) -> str:
        """Inspects text for verse keys (e.g. 2:255) and fetches exact JSON content."""
        parsed = QURAN_DB.parse_verse_key(text)
        if not parsed:
            return ""

        surah_num, start_ayah, end_ayah = parsed
        end_v = end_ayah if end_ayah else start_ayah
        verses = QURAN_DB.get_range(surah_num, start_ayah, end_v)

        if not verses:
            return ""

        header = f"--- QS. Surah {surah_num}:{start_ayah}" + (f"-{end_v} ---" if start_ayah != end_v else " ---")
        details = []
        for v in verses:
            details.append(
                f"Arabic Text ({v['ayah_num']}): {v['ar']}\n"
                f"Official JSON Translation Reference ({v['ayah_num']}): {v['tr']}"
            )

        return (
            "\n\n[OFFICIAL QURAN DATA INJECTED FROM LOCAL JSON FILES]\n"
            "CRITICAL TRANSLATION INSTRUCTIONS FOR GROQ:\n"
            "1. ARABIC TEXT: Use the EXACT Arabic Quran text provided below verbatim from 'qpc-hafs.json'. DO NOT generate or alter Arabic Quranic text from memory.\n"
            "2. TRANSLATION GROUNDING: Use the 'Official JSON Translation Reference' provided below directly as ground truth. Translate and adapt this reference text naturally to match the required target response language.\n\n"
            + header + "\n" + "\n".join(details) +
            "\n[END OF OFFICIAL QURAN DATA]\n"
        )
#endregion

#region Discord Events
class IslamicBot(commands.Bot):
    """Production Discord Bot with HTTP keep-alive, tasks, and slash commands."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.groq_client: Optional[GroqClient] = None
        self.user_languages: Dict[int, str] = {}

    async def setup_hook(self):
        """Asynchronous initialization hook."""
        self.session = aiohttp.ClientSession()
        self.groq_client = GroqClient(self.session)
        
        # Load local Quran JSON Databases
        QURAN_DB.load_data()
        
        # Sync Slash Commands
        try:
            synced = await self.tree.sync()
            LOGGER.info(f"Synced {len(synced)} Slash Commands for Islamic.AI Bot!")
        except Exception as e:
            LOGGER.error(f"Failed to sync slash commands: {e}")

        # Start background ping task
        if not self.keep_alive_ping.is_running():
            self.keep_alive_ping.start()

    async def close(self):
        """Gracefully closes HTTP session."""
        if self.session:
            await self.session.close()
        await super().close()

    @tasks.loop(hours=2)
    async def keep_alive_ping(self):
        """Background loop for Streamlit keep-alive ping."""
        if CONFIG.STREAMLIT_URL and "streamlit.app" in CONFIG.STREAMLIT_URL and self.session:
            try:
                async with self.session.get(CONFIG.STREAMLIT_URL, timeout=15) as resp:
                    LOGGER.info(f"[Keep-Alive] Ping to Streamlit ({CONFIG.STREAMLIT_URL}) status: {resp.status}")
            except Exception as e:
                LOGGER.warning(f"[Keep-Alive] Ping to Streamlit failed: {e}")

    @keep_alive_ping.before_loop
    async def before_keep_alive(self):
        await self.wait_until_ready()

BOT = IslamicBot()

@BOT.event
async def on_ready():
    LOGGER.info(f"Islamic.AI Bot ({BOT.user}) is Online!")
    await BOT.change_presence(
        activity=discord.Game(name="/help | /quran | /fiqh | /tafsir")
    )

@BOT.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Check for direct Verse Shortcut (e.g., 2:255 or 1:1-7)
    parsed_verse = QURAN_DB.parse_verse_key(message.content.strip())
    if parsed_verse and len(message.content.strip().split()) == 1:
        surah_num, start_a, end_a = parsed_verse
        await send_quran_embed(message.channel, surah_num, start_a, end_a, reply_msg=message)
        return

    # Check mention or reply to bot
    is_reply_to_bot = False
    if message.reference and message.reference.message_id:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.author == BOT.user:
                is_reply_to_bot = True
        except Exception:
            pass

    is_mentioned = BOT.user in message.mentions

    if is_reply_to_bot or is_mentioned:
        async with message.channel.typing():
            raw_history = []
            async for msg in message.channel.history(limit=8):
                clean_text = msg.content.replace(f"<@{BOT.user.id}>", "").strip()
                if not clean_text:
                    continue
                if msg.author == BOT.user:
                    raw_history.append(f"Assistant: {clean_text}")
                elif not msg.author.bot:
                    sender_name = msg.author.display_name
                    raw_history.append(f"User [{sender_name}]: {clean_text}")

            raw_history.reverse()
            last_prompt = raw_history[-1] if raw_history else message.content
            
            web_ref = await SmartSearch.execute_search(BOT.session, last_prompt)
            quran_ctx = PromptBuilder.extract_quran_context(last_prompt)
            
            user_lang = BOT.user_languages.get(message.author.id)
            lang_instruction = PromptBuilder.create_language_instruction(user_lang)

            prompt = (
                f"VERIFIED WEB REFERENCES:\n{web_ref}\n\n"
                f"{quran_ctx}\n"
                f"CHAT HISTORY:\n" + "\n".join(raw_history) + "\n\n"
                f"[MANDATORY REQUIREMENT: Your answer MUST contain: (1) Relevant Arabic Dalil text + translation grounded in the provided JSON, and (2) Explicit book/scholarly source citations.]{lang_instruction}"
            )

            jawaban = await BOT.groq_client.chat_completion(
                prompt_text=prompt,
                system_prompt=PromptBuilder.SYSTEM_PROMPT,
                preferred_model=CONFIG.MODEL_LIGHT
            )
            await send_long_message(message, jawaban, mode="reply")

    await BOT.process_commands(message)
#endregion

#region Reusable Helpers
async def send_long_message(target: Any, text: str, mode: str = "reply"):
    """Splits and sends long responses safely without cutting words in half."""
    if not text:
        return
    
    limit = 1800
    chunks = []
    
    while len(text) > limit:
        cut_index = text.rfind(' ', 0, limit)
        if cut_index == -1:
            cut_index = limit
            
        chunks.append(text[:cut_index])
        text = text[cut_index:].strip()
        
    if text:
        chunks.append(text)

    for i, chunk in enumerate(chunks):
        if mode == "reply":
            if i == 0 and hasattr(target, "reply"):
                await target.reply(chunk)
            else:
                channel = getattr(target, "channel", target)
                await channel.send(chunk)
        elif mode == "slash":
            if hasattr(target, "followup"):
                await target.followup.send(chunk)
            elif hasattr(target, "send_message"):
                await target.send_message(chunk)

async def send_quran_embed(destination: Any, surah_num: int, start_ayah: int, end_ayah: Optional[int] = None, reply_msg: Optional[discord.Message] = None):
    """Generates pure zero-hallucination Embed directly from local Quran JSON database."""
    end_v = end_ayah if end_ayah else start_ayah
    verses = QURAN_DB.get_range(surah_num, start_ayah, end_v)

    if not verses:
        msg = f"❌ Verse QS {surah_num}:{start_ayah} not found! Please verify Surah (1-114) and Ayah numbers."
        if reply_msg:
            await reply_msg.reply(msg)
        elif hasattr(destination, "followup"):
            await destination.followup.send(msg)
        else:
            await destination.send(msg)
        return

    surah_name = verses[0]["surah_name"]
    title_ref = f"📖 QS. {surah_name} [{surah_num}:{start_ayah}" + (f"-{end_v}]" if start_ayah != end_v else "]")
    
    embed = discord.Embed(title=title_ref, color=discord.Color.gold())
    
    arab_texts = []
    trans_texts = []
    for v in verses:
        arab_texts.append(f"({v['ayah_num']}) {v['ar']}")
        trans_texts.append(f"**[{v['ayah_num']}]** {v['tr']}")

    embed.add_field(name="Arabic Text (qpc-hafs.json)", value="\n".join(arab_texts)[:1024], inline=False)
    embed.add_field(name="JSON Reference Translation", value="\n".join(trans_texts)[:1024], inline=False)
    embed.set_footer(text="Source: Official Local JSON Database (Zero AI Hallucination)")

    if reply_msg:
        await reply_msg.reply(embed=embed)
    elif hasattr(destination, "followup"):
        await destination.followup.send(embed=embed)
    else:
        await destination.send(embed=embed)

async def process_slash_query(
    interaction: discord.Interaction,
    prompt: str,
    language: Optional[str] = None,
    model_override: str = CONFIG.MODEL_LIGHT
):
    """Generic processor for slash commands with rate limiting and caching."""
    user_id = interaction.user.id
    
    # Check rate limit
    is_limited, remaining = await GLOBAL_RATE_LIMITER.is_rate_limited(user_id)
    if is_limited:
        await interaction.followup.send(f"⏱️ Please slow down! Try again in {remaining:.1f} seconds.")
        return

    try:
        sender_name = interaction.user.display_name
        web_ref = await SmartSearch.execute_search(BOT.session, prompt)
        quran_ctx = PromptBuilder.extract_quran_context(prompt)
        
        # Priority: explicit command language param > user saved language preference
        chosen_lang = language or BOT.user_languages.get(user_id)
        lang_instruction = PromptBuilder.create_language_instruction(chosen_lang)

        final_prompt = (
            f"[{sender_name}]: {prompt}\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}\n"
            f"{quran_ctx}\n"
            f"[MANDATORY REQUIREMENT: You MUST include: (1) Relevant Arabic Dalil text with translation grounded in the provided JSON dataset, and (2) Explicit classical/contemporary Fiqh or Tafsir book citation.]{lang_instruction}"
        )

        jawaban = await BOT.groq_client.chat_completion(
            prompt_text=final_prompt,
            system_prompt=PromptBuilder.SYSTEM_PROMPT,
            preferred_model=model_override
        )
        await send_long_message(interaction, jawaban, mode="slash")
    except Exception as e:
        LOGGER.error(f"Error processing query '{prompt}': {e}")
        await interaction.followup.send(f"⚠️ An error occurred while processing your request: {e}")
#endregion# ==============================================================================
# bot_quran.py - Production-Ready Islamic & Quran Discord AI Bot (PART 4)
# ==============================================================================

#region Commands
@BOT.tree.command(name="help", description="Guide & command list for Islamic.AI Bot")
@app_commands.describe(
    language="Optional: Type target response language (e.g. English, French, Arabic, Spanish)"
)
async def slash_help(interaction: discord.Interaction, language: Optional[str] = None):
    guide_text = (
        "📖 **Islamic.AI — Command Guide & Help**\n\n"
        "**Main Commands (Strictly Grounded with Dalil & Sources):**\n"
        "• `/quran [surah] [verse] [verse_to] [language]` - Fetch exact Arabic & Reference Translation directly from JSON Database (0% Hallucination).\n"
        "• `/ask [prompt] [language]` - Ask any question (Includes Arabic Dalil + Kitāb citations).\n"
        "• `/tafsir [verse] [source] [language]` - Detailed Qur'anic exegesis powered by JSON Data + AI.\n"
        "• `/fiqh [question] [madhhab] [language]` - Ask Fiqh rulings with Arabic Dalil & Fiqh book sources.\n"
        "• `/hadith [topic] [book] [language]` - Search authentic Hadiths with Matan Arabic & collection citations.\n"
        "• `/dua [topic] [language]` - Search authentic Duas with Arabic text & source references.\n"
        "• `/dalil [topic] [language]` - Find evidence from Qur'an & Sunnah (Arabic + Translation + Citations).\n"
        "• `/search [query] [language]` - Search live web references with cited sources.\n"
        "• `/language [language]` - Save your preferred default language for all responses.\n"
        "• `/test [language]` - Check Groq API connection, latency, & system health.\n"
        "• `/ping` - Check bot status and Discord latency.\n\n"
        "💡 *Verse Shortcut Tip:* Type verse numbers like `1:1-7` or `2:255` directly in chat to view Arabic text & translation instantly!\n"
        "💡 *Language Tip:* Every command now features a `language` option! The bot also automatically detects your question's language.\n\n"
        "--------------------------------------------------\n"
        "📌 **NB:** If you encounter AI hallucinations or problems with the AI bot, please contact **@hanabihikari** via DM with a screenshot."
    )
    if language:
        BOT.user_languages[interaction.user.id] = language
    await interaction.response.send_message(guide_text)

@BOT.tree.command(name="quran", description="Get exact Qur'an Arabic text and reference translation directly from database")
@app_commands.describe(
    surah="Surah number (1-114)",
    verse="Verse number",
    verse_to="Optional: Ending verse range (e.g., 7 for verses 1-7)",
    language="Optional: Type target response language (e.g., English, French, Arabic, Spanish)"
)
async def slash_quran(
    interaction: discord.Interaction, 
    surah: int, 
    verse: int, 
    verse_to: Optional[int] = None,
    language: Optional[str] = None
):
    await interaction.response.defer()
    if language:
        BOT.user_languages[interaction.user.id] = language
    await send_quran_embed(interaction, surah, verse, verse_to)

@BOT.tree.command(name="ask", description="Ask anything about Islam (Arabic Dalil & Book Citations Included)")
@app_commands.describe(
    prompt="Your question or topic",
    language="Optional: Type target response language (e.g., English, French, Arabic, Spanish)"
)
async def slash_ask(
    interaction: discord.Interaction, 
    prompt: str, 
    language: Optional[str] = None
):
    await interaction.response.defer()
    await process_slash_query(interaction, prompt, language, CONFIG.MODEL_LIGHT)

@BOT.tree.command(name="tafsir", description="Detailed Qur'anic exegesis (Injected with Official JSON Data)")
@app_commands.describe(
    verse="Verse reference (e.g., '2:255')",
    source="Optional: Tafsir book (Ibn Kathir, Jalalayn, etc.)",
    language="Optional: Type target response language (e.g., English, French, Arabic, Spanish)"
)
async def slash_tafsir(
    interaction: discord.Interaction, 
    verse: str, 
    source: Optional[str] = None,
    language: Optional[str] = None
):
    await interaction.response.defer()
    query = f"Provide a comprehensive tafsir for verse {verse}. Primary reference requested: {source if source else 'Tafsir Ibn Kathir / Jalalayn'}."
    await process_slash_query(interaction, query, language, CONFIG.MODEL_HEAVY)

@BOT.tree.command(name="fiqh", description="Ask Fiqh rulings with Arabic Dalil & Kitāb sources")
@app_commands.describe(
    question="Your jurisprudence (Fiqh) question",
    madhhab="Select Madhhab perspective",
    language="Optional: Type target response language (e.g., English, French, Arabic, Spanish)"
)
@app_commands.choices(
    madhhab=[
        app_commands.Choice(name="Shafi'i", value="shafii"),
        app_commands.Choice(name="Hanafi", value="hanafi"),
        app_commands.Choice(name="Maliki", value="maliki"),
        app_commands.Choice(name="Hanbali", value="hanbali"),
        app_commands.Choice(name="Ja'fari / Shia Twelver", value="jaafari_shia"),
        app_commands.Choice(name="Zaidi / Shia Zaidiyyah", value="zaidi_shia"),
        app_commands.Choice(name="Comparative (All Schools of Thought)", value="comparative_all")
    ]
)
async def slash_fiqh(
    interaction: discord.Interaction, 
    question: str, 
    madhhab: Optional[app_commands.Choice[str]] = None,
    language: Optional[str] = None
):
    await interaction.response.defer()
    chosen_madhhab = madhhab.value if madhhab else "comparative_all"
    query = f"Fiqh Question: '{question}'. Requested Madhhab: {chosen_madhhab.upper()}."
    await process_slash_query(interaction, query, language, CONFIG.MODEL_HEAVY)

@BOT.tree.command(name="hadith", description="Search authentic Hadiths with Arabic Matan & Collection Citations")
@app_commands.describe(
    topic="Hadith topic or keyword",
    book="Optional: Hadith Collection (Bukhari, Muslim, Abu Dawud, etc.)",
    language="Optional: Type target response language (e.g., English, French, Arabic, Spanish)"
)
async def slash_hadith(
    interaction: discord.Interaction, 
    topic: str, 
    book: Optional[str] = None,
    language: Optional[str] = None
):
    await interaction.response.defer()
    query = f"Search authentic Hadiths regarding '{topic}'. Requested Collection: {book if book else 'Kutubus Sittah'}."
    await process_slash_query(interaction, query, language, CONFIG.MODEL_LIGHT)

@BOT.tree.command(name="dua", description="Search authentic Duas and Adhkar with Arabic Text & Sources")
@app_commands.describe(
    topic="Topic or situation for the Dua",
    language="Optional: Type target response language (e.g., English, French, Arabic, Spanish)"
)
async def slash_dua(
    interaction: discord.Interaction, 
    topic: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    query = f"Provide authentic Duas for topic/situation: '{topic}'."
    await process_slash_query(interaction, query, language, CONFIG.MODEL_LIGHT)

@BOT.tree.command(name="dalil", description="Find Qur'anic and Hadith evidence (Arabic + Translation + Sources)")
@app_commands.describe(
    topic="Topic or issue to search evidence for",
    language="Optional: Type target response language (e.g., English, French, Arabic, Spanish)"
)
async def slash_dalil(
    interaction: discord.Interaction, 
    topic: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    query = f"Provide authentic Dalil (Qur'an verses and Sahih Hadiths) for topic: '{topic}'."
    await process_slash_query(interaction, query, language, CONFIG.MODEL_LIGHT)

@BOT.tree.command(name="search", description="Search Islamic research references from the web with citations")
@app_commands.describe(
    query="Search keywords",
    language="Optional: Type target response language (e.g., English, French, Arabic, Spanish)"
)
async def slash_search(
    interaction: discord.Interaction, 
    query: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    await process_slash_query(interaction, query, language, CONFIG.MODEL_LIGHT)

@BOT.tree.command(name="language", description="Set your preferred default response language")
@app_commands.describe(language="Language name e.g. English, French, Arabic, Spanish, German")
async def slash_language(interaction: discord.Interaction, language: str):
    BOT.user_languages[interaction.user.id] = language
    await interaction.response.send_message(f"✅ Your preferred response language has been set to: **{language}**")

@BOT.tree.command(name="test", description="Test Groq API connection, latency, and system health")
@app_commands.describe(
    language="Optional: Type target response language (e.g. English, French, Arabic)"
)
async def slash_test(interaction: discord.Interaction, language: Optional[str] = None):
    await interaction.response.defer()
    try:
        start_time = time.time()
        
        target_lang = language or BOT.user_languages.get(interaction.user.id) or "English"
        test_prompt = f"System test: Provide 1 short Islamic greeting in {target_lang}."
        
        respon = await BOT.groq_client.chat_completion(
            prompt_text=test_prompt,
            system_prompt="You are a system tester.",
            preferred_model=CONFIG.MODEL_LIGHT
        )
        api_latency = round((time.time() - start_time) * 1000)
        discord_ping = round(BOT.latency * 1000)
        
        db_status = "Connected & Loaded" if QURAN_DB.is_loaded else "Not Loaded (Fallback Active)"

        status_msg = (
            "🧪 **[SYSTEM DIAGNOSTIC - ISLAMIC.AI]**\n\n"
            f"🟢 **Groq API Status:** Connected & Active\n"
            f"📖 **Quran Dual JSON Database:** `{db_status}`\n"
            f"⚡ **API Latency:** `{api_latency}ms`\n"
            f"📡 **Discord Ping:** `{discord_ping}ms`\n"
            f"🧠 **Active Engine:** Global Dual-JSON Grounding RAG (`{CONFIG.MODEL_LIGHT}`)\n"
            f"⏰ **Streamlit Keep-Alive:** Active (`{CONFIG.STREAMLIT_URL}`)\n\n"
            f"💬 **Output Test Sample ({target_lang}):**\n> {respon}"
        )
        await interaction.followup.send(status_msg)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Diagnostic test failed: {e}")

@BOT.tree.command(name="ping", description="Check bot latency status")
async def slash_ping(interaction: discord.Interaction):
    latency = round(BOT.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Islamic.AI latency: `{latency}ms` (Dual JSON Grounding Active)")
#endregion

#region Main
async def start_web_server():
    """Starts a minimal keep-alive HTTP server for Render/Railway/Streamlit Cloud hosting."""
    async def handle_ping(request):
        return web.Response(text="Quran AI Discord Bot is alive!", status=200)

    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", CONFIG.PORT)
    await site.start()
    LOGGER.info(f"Keep-alive web server bound to port {CONFIG.PORT}")

async def main():
    """Main execution entrypoint."""
    if not CONFIG.DISCORD_TOKEN:
        LOGGER.critical("DISCORD_TOKEN environment variable or Streamlit Secret missing! Exiting...")
        return

    # Start Keep-Alive Web Server
    await start_web_server()

    # Start Discord Bot
    try:
        await BOT.start(CONFIG.DISCORD_TOKEN)
    except KeyboardInterrupt:
        LOGGER.info("Shutdown requested...")
    finally:
        await BOT.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("Bot execution terminated.")
#endregion
