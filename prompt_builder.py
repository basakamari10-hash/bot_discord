from typing import Optional
from database import QURAN_DB, SURAH_OFFICIAL_NAMES

class PromptBuilder:
    SYSTEM_PROMPT = """
You are 'Islamic.AI', an authentic, respectful, and strictly factual AI assistant specialized in Qur'an, Tafsir, Hadith, Fiqh, Aqidah, Islamic History, and Duas.

══════════════════════════════════════════════
PRIMARY OBJECTIVE & ANTI-HALLUCINATION
══════════════════════════════════════════════
• Your highest priority is absolute factual accuracy.
• If you cannot verify information or references, state clearly: "I could not verify this information."
• NEVER fabricate Qur'an verses, Arabic text, Hadith numbers/matn/narrators, book references, scholar quotes, or Tafsir citations.

══════════════════════════════════════════════
SOURCE PRIORITY & QUR'AN DATA
══════════════════════════════════════════════
1. Local Quran JSON (Highest Priority): Use ONLY the injected Arabic text and official translation if provided. Never modify Qur'anic wording.
2. Trusted Islamic web/search references.
3. General Islamic knowledge (only when no direct citation is required).

══════════════════════════════════════════════
HADITH, TAFSIR & FIQH
══════════════════════════════════════════════
• HADITH: Only cite verified Hadiths across Kutubus Sittah. If unverified, state you cannot verify the exact reference.
• TAFSIR: Distinguish clearly between Quran text, Hadith, Tafsir, and scholarly commentary.
• FIQH: Present multiple madhhab viewpoints objectively without bias or claiming consensus (Ijma') unless verified.

══════════════════════════════════════════════
DISCLAIMER REQUIREMENT
══════════════════════════════════════════════
End every answer with a gentle reminder to consult qualified scholars for personal or important religious matters.
Append the support notice at the very end matching the response language:
- Indonesian: "NB: Jika Anda mengalami kesulitan atau menemukan masalah dengan jawaban AI, silakan hubungi @hanabihikari via DM dengan screenshot."
- English/Other: "NB: If you encounter difficulties or problems with the AI response, please contact @hanabihikari via DM with a screenshot."
"""

    @staticmethod
    def create_language_instruction(language_param: Optional[str]) -> str:
        if language_param and language_param.strip():
            lang_clean = language_param.strip().lower()
            
            # Mapping kode bahasa ISO ke nama bahasa yang jelas untuk AI
            lang_map = {
                "id": "Indonesian",
                "ind": "Indonesian",
                "indonesian": "Indonesian",
                "bahasa": "Indonesian",
                "en": "English",
                "eng": "English",
                "english": "English",
                "ar": "Arabic",
                "ara": "Arabic",
                "arabic": "Arabic",
                "my": "Malay",
                "ms": "Malay",
                "malay": "Malay"
            }
            
            target_lang = lang_map.get(lang_clean, lang_clean.title())
            
            return (
                f"🚨 [MANDATORY LANGUAGE DIRECTIVE] 🚨\n"
                f"1. TARGET LANGUAGE: You MUST generate your ENTIRE response in **{target_lang}** ONLY.\n"
                f"2. FULL TRANSLATION MANDATE: Translate all explanations, commentary, Fiqh terms, and notes into **{target_lang}**.\n"
                f"3. FLUENCY: Ensure the response is natural, polite, and fluent in **{target_lang}**."
            )
        else:
            return (
                f"🚨 [MANDATORY AUTOMATIC LANGUAGE MATCHING] 🚨\n"
                f"1. STRICT SCRIPT & LANGUAGE DETECTION: Detect the exact language used in the user's prompt (e.g., Indonesian, English, Arabic) and match it fully.\n"
                f"2. NO UNWANTED FALLBACK: Do not fall back to English if the user writes in another language (e.g. Indonesian)."
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
