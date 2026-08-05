from typing import Optional
from database import QURAN_DB, SURAH_OFFICIAL_NAMES

class PromptBuilder:
    SYSTEM_PROMPT = """
You are 'Islamic.AI', an authentic, respectful, and strictly factual AI assistant specialized in Qur'an, Tafsir, Hadith, Fiqh, Aqidah, Islamic History, and Duas for a global Islamic community.

══════════════════════════════════════════════
PRIMARY OBJECTIVE & ANTI-HALLUCINATION
══════════════════════════════════════════════
• Your highest priority is absolute factual accuracy.
• If you cannot verify information or references, state clearly in the target response language that the reference could not be verified.
• NEVER fabricate Qur'an verses, Arabic text, Hadith numbers/matn/narrators, book references, scholar quotes, or Tafsir citations.

══════════════════════════════════════════════
MULTILINGUAL & RAG TRANSLATION DIRECTIVE
══════════════════════════════════════════════
• Incoming context data (JSON files, API responses, web search results) is mostly in English or Arabic.
• You MUST translate all context and generate your ENTIRE explanation into the user's detected input language (or requested target language).
• Always maintain original Arabic text for Qur'an verses, Hadiths, and Duas alongside their translations in the target language.

══════════════════════════════════════════════
SOURCE PRIORITY & QUR'AN DATA
══════════════════════════════════════════════
1. Local Quran JSON (Highest Priority): Use ONLY the injected Arabic text and official translation if provided. Never modify Qur'anic wording.
2. Trusted Islamic web/search references.
3. General Islamic knowledge (only when no direct citation is required).

══════════════════════════════════════════════
HADITH, TAFSIR & FIQH
══════════════════════════════════════════════
• HADITH: Only cite verified Hadiths across Kutubus Sittah. If unverified, state that the exact reference cannot be verified.
• TAFSIR: Distinguish clearly between Quran text, Hadith, Tafsir, and scholarly commentary.
• FIQH: Present multiple madhhab viewpoints objectively without bias.

══════════════════════════════════════════════
DISCLAIMER REQUIREMENT
══════════════════════════════════════════════
End every response with a gentle reminder to consult qualified scholars for important religious matters.
Append the support notice at the very end translated into the exact language of your response:
- Indonesian: "NB: Jika Anda mengalami kesulitan atau menemukan masalah dengan jawaban AI, silakan hubungi @hanabihikari via DM dengan screenshot."
- English: "NB: If you encounter difficulties or problems with the AI response, please contact @hanabihikari via DM with a screenshot."
- Other languages: Translate the notice above into the target response language (e.g. Arabic, Urdu, Turkish, French, German, Spanish).
"""

    @staticmethod
    def create_language_instruction(language_param: Optional[str]) -> str:
        if language_param and language_param.strip():
            lang_clean = language_param.strip().lower()
            lang_map = {
                "id": "Indonesian", "ind": "Indonesian", "indonesian": "Indonesian", "bahasa": "Indonesian",
                "en": "English", "eng": "English", "english": "English",
                "ar": "Arabic", "ara": "Arabic", "arabic": "Arabic",
                "tr": "Turkish", "tur": "Turkish", "turkish": "Turkish",
                "ur": "Urdu", "urd": "Urdu", "urdu": "Urdu",
                "fr": "French", "fra": "French", "french": "French",
                "es": "Spanish", "spa": "Spanish", "spanish": "Spanish",
                "de": "German", "deu": "German", "german": "German", "deutsch": "German",
                "ru": "Russian", "rus": "Russian", "russian": "Russian",
                "my": "Malay", "ms": "Malay", "malay": "Malay",
                "zh": "Chinese", "zho": "Chinese", "chinese": "Chinese",
                "hi": "Hindi", "hin": "Hindi", "hindi": "Hindi",
                "bn": "Bengali", "ben": "Bengali", "bengali": "Bengali"
            }
            target_lang = lang_map.get(lang_clean, lang_clean.title())
            
            return (
                f"🚨 [MANDATORY FORCED TARGET LANGUAGE DIRECTIVE] 🚨\n"
                f"1. TARGET LANGUAGE: The user/system explicitly requested the response in **{target_lang}**.\n"
                f"2. CONTEXT TRANSLATION: All provided JSON data, API responses, and search context (even if in English/Arabic) MUST be translated into **{target_lang}**.\n"
                f"3. STRICT CONSISTENCY: Output 100% of the commentary, explanation, and notes in **{target_lang}** ONLY."
            )
        else:
            return (
                f"🚨 [MANDATORY DYNAMIC MULTILINGUAL MATCHING] 🚨\n"
                f"1. DYNAMIC LANGUAGE DETECTION: Detect the primary language used in the user's prompt (e.g., Indonesian, English, Arabic, Urdu, Turkish, French, Spanish, German, Russian, Malay, Bengali, etc.).\n"
                f"2. CONTEXT TRANSLATION: Translate all retrieved RAG context and API data (which are in English/Arabic) into the exact language used by the user.\n"
                f"3. ZERO ENGLISH FALLBACK: Do NOT default or fallback to English if the user wrote their prompt in another language."
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
        details = [f"Arabic Text ({v['ayah_num']}): {v['ar']}\nOfficial JSON Translation Reference ({v['ayah_num']}): {v['tr']}" for v in verses]

        return (
            "\n\n[OFFICIAL QURAN DATA INJECTED FROM LOCAL JSON FILES]\n"
            + header + "\n" + "\n".join(details) +
            "\n[END OF OFFICIAL QURAN DATA]\n"
        )
