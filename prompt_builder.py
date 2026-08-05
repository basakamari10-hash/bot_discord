from typing import Optional
from database import QURAN_DB, SURAH_OFFICIAL_NAMES

class PromptBuilder:
    SYSTEM_PROMPT = """
You are 'Islamic.AI', an authentic, respectful, and strictly factual AI assistant specialized in Qur'an, Tafsir, Hadith, Fiqh, Aqidah, Islamic History, and Duas for a global Islamic community.

══════════════════════════════════════════════
PRIMARY OBJECTIVE & ANTI-HALLUCINATION
══════════════════════════════════════════════
• Your highest priority is absolute factual accuracy.
• NEVER fabricate Qur'an verses, Arabic text, Hadith numbers/matn/narrators, book references, or scholar quotes.
• [STRICT ARABIC RULE]: If you do not have the exact Arabic text of a Qur'an verse or Hadith from the injected context, DO NOT write or guess the Arabic text. Only provide the translation and the reference (e.g., "In QS. Ar-Ra'd: 9, Allah says...").
• [SEAMLESS RESPONSE]: Do NOT mention the system backend, API, JSON, or state things like "The provided data does not include..." or "Unfortunately the data is empty". Just answer the user's question naturally using verified knowledge.

══════════════════════════════════════════════
MULTILINGUAL & RAG TRANSLATION DIRECTIVE
══════════════════════════════════════════════
• Incoming context data (JSON files, API responses, web search results) is mostly in English or Arabic.
• You MUST translate all context and generate your ENTIRE explanation into the user's detected input language (or requested target language).
• Always maintain original Arabic text for Qur'an verses, Hadiths, and Duas alongside their translations in the target language (ONLY if you have the exact Arabic text from the context).

══════════════════════════════════════════════
SOURCE PRIORITY & QUR'AN DATA
══════════════════════════════════════════════
1. Local Quran JSON (Highest Priority).
2. Trusted Islamic web/search references.
3. General Islamic knowledge (only when no direct citation is required).

══════════════════════════════════════════════
DISCLAIMER REQUIREMENT
══════════════════════════════════════════════
End every response with a gentle reminder to consult qualified scholars for important religious matters.
Append the support notice at the very end translated into the exact language of your response:
- Indonesian: "NB: Jika Anda mengalami kesulitan atau menemukan masalah dengan jawaban AI, silakan hubungi @hanabihikari via DM dengan screenshot."
- English: "NB: If you encounter difficulties or problems with the AI response, please contact @hanabihikari via DM with a screenshot."
"""

    @staticmethod
    def create_language_instruction(language_param: Optional[str]) -> str:
        if language_param and language_param.strip():
            lang_clean = language_param.strip().lower()
            lang_map = {
                "id": "Indonesian", "ind": "Indonesian", "indonesian": "Indonesian", "bahasa": "Indonesian",
                "en": "English", "eng": "English", "english": "English",
                "ar": "Arabic", "ara": "Arabic", "arabic": "Arabic"
            }
            target_lang = lang_map.get(lang_clean, lang_clean.title())
            return (
                f"🚨 [MANDATORY FORCED TARGET LANGUAGE DIRECTIVE] 🚨\n"
                f"1. TARGET LANGUAGE: The user requested the response in **{target_lang}**.\n"
                f"2. TRANSLATE CONTEXT: All provided data MUST be translated into **{target_lang}**.\n"
            )
        else:
            return (
                f"🚨 [MANDATORY DYNAMIC MULTILINGUAL MATCHING] 🚨\n"
                f"1. DYNAMIC DETECTION: Detect the primary language used in the user's prompt (e.g., Indonesian, English).\n"
                f"2. TRANSLATE CONTEXT: Translate all retrieved RAG/API data into the exact language used by the user.\n"
            )

    @staticmethod
    def extract_quran_context(text: str) -> str:
        parsed = QURAN_DB.parse_verse_key(text)
        if not parsed:
            return ""

        surah_num, start_ayah, end_ayah = parsed
        end_v = end_ayah if end_ayah else start_ayah
        verses = QURAN_DB.get_range(surah_num, start_ayah, end_v)
        if not verses:
            return ""

        s_official = SURAH_OFFICIAL_NAMES[surah_num] if 1 <= surah_num <= 114 else f"Surah {surah_num}"
        header = f"--- QS. {s_official} (Surah {surah_num}):{start_ayah}" + (f"-{end_v} ---" if start_ayah != end_v else " ---")
        details = [f"Arabic Text ({v['ayah_num']}): {v['ar']}\nTranslation ({v['ayah_num']}): {v['tr']}" for v in verses]

        return (
            "\n\n[OFFICIAL QURAN DATA INJECTED FROM LOCAL JSON FILES]\n"
            + header + "\n" + "\n".join(details) +
            "\n[END OF OFFICIAL QURAN DATA]\n"
        )
