import os
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from config import CONFIG
from logger import LOGGER

SURAH_MAP: Dict[str, int] = {
    # 1-10
    "fatihah": 1, "fatiha": 1, "الفاتحة": 1,
    "baqarah": 2, "baqara": 2, "bakara": 2, "البقرة": 2,
    "imran": 3, "ali-imran": 3, "آل عمران": 3,
    "nisa": 4, "nisaa": 4, "النساء": 4,
    "maidah": 5, "maida": 5, "المائدة": 5,
    "anam": 6, "an'am": 6, "الأنعام": 6,
    "araf": 7, "a'raf": 7, "الأعراف": 7,
    "anfal": 8, "الأنفال": 8,
    "taubah": 9, "tawbah": 9, "tevbe": 9, "التوبة": 9,
    "yunus": 10, "yunas": 10, "يونس": 10,
    # 11-20
    "hud": 11, "هود": 11,
    "yusuf": 12, "joseph": 12, "يوسف": 12,
    "rad": 13, "ra'd": 13, "الرعد": 13,
    "ibrahim": 14, "abraham": 14, "إبراهيم": 14,
    "hijr": 15, "الحجر": 15,
    "nahl": 16, "النحل": 16,
    "isra": 17, "الإسراء": 17,
    "kahf": 18, "kahfi": 18, "kehf": 18, "الكهف": 18,
    "maryam": 19, "mary": 19, "مريم": 19,
    "taha": 20, "ta-ha": 20, "طه": 20,
    # 21-30
    "anbiya": 21, "anbiya'": 21, "الأنبيائ": 21,
    "hajj": 22, "hac": 22, "الحج": 22,
    "muminun": 23, "mu'minun": 23, "المؤمنون": 23,
    "nur": 24, "noor": 24, "النور": 24,
    "furqan": 25, "الفرقان": 25,
    "shuara": 26, "shu'ara": 26, "الشعراء": 26,
    "naml": 27, "النمل": 27,
    "qasas": 28, "القصص": 28,
    "ankabut": 29, "'ankabut": 29, "العنكبوت": 29,
    "rum": 30, "الروم": 30,
    # 31-40
    "luqman": 31, "lokman": 31, "لقمان": 31,
    "sajdah": 32, "secde": 32, "السجدة": 32,
    "ahzab": 33, "الأحزاب": 33,
    "saba": 34, "saba'": 34, "سبأ": 34,
    "fatir": 35, "فاطر": 35,
    "yasin": 36, "ya-sin": 36, "yaseen": 36, "يس": 36,
    "saffat": 37, "الصافات": 37,
    "sad": 38, "ص": 38,
    "zumar": 39, "الزمر": 39,
    "ghafir": 40, "mumin": 40, "غافر": 40,
    # 41-50
    "fussilat": 41, "فصلت": 41,
    "shura": 42, "shuraa": 42, "الشورى": 42,
    "zukhruf": 43, "الزخرف": 43,
    "dukhan": 44, "الدخان": 44,
    "jathiyah": 45, "جاثية": 45, "الجاثية": 45,
    "ahqaf": 46, "الأحقاف": 46,
    "muhammad": 47, "محمد": 47,
    "fath": 48, "fetih": 48, "الفتح": 48,
    "hujurat": 49, "الحجرات": 49,
    "qaf": 50, "ق": 50,
    # 51-60
    "dhariyat": 51, "zariyat": 51, "الذاريات": 51,
    "tur": 52, "الطور": 52,
    "najm": 53, "necm": 53, "النجم": 53,
    "qamar": 54, "القمر": 54,
    "rahman": 55, "الرحمن": 55,
    "waqiah": 56, "waqi'ah": 56, "vakaa": 56, "الواقعة": 56,
    "hadid": 57, "الحديد": 57,
    "mujadila": 58, "mujadilah": 58, "المجادلة": 58,
    "hashr": 59, "الحشر": 59,
    "mumtahanah": 60, "الممتحنة": 60,
    # 61-70
    "saff": 61, "الصف": 61,
    "jumuah": 62, "jumu'ah": 62, "cuma": 62, "الجمعة": 62,
    "munafiqun": 63, "المنافقون": 63,
    "taghabun": 64, "التغابن": 64,
    "talaq": 65, "التلاق": 65,
    "tahrim": 66, "التحريم": 66,
    "mulk": 67, "tebareke": 67, "الملك": 67,
    "qalam": 68, "kalem": 68, "القلم": 68,
    "haqqah": 69, "الحاقة": 69,
    "maarij": 70, "ma'arij": 70, "المعارج": 70,
    # 71-80
    "nuh": 71, "noah": 71, "نوح": 71,
    "jinn": 72, "cin": 72, "الجن": 72,
    "muzzammil": 73, "المزمل": 73,
    "muddaththir": 74, "المدثر": 74,
    "qiyamah": 75, "قيامة": 75, "القيامة": 75,
    "insan": 76, "dahr": 76, "الإنسان": 76,
    "mursalat": 77, "المرسلات": 77,
    "naba": 78, "nebe": 78, "النبأ": 78,
    "naziat": 79, "nazi'at": 79, "النازعات": 79,
    "abasa": 80, "عبس": 80,
    # 81-90
    "takwir": 81, "التكوير": 81,
    "infitar": 82, "الانفطار": 82,
    "mutaffifin": 83, "المطففين": 83,
    "inshiqaq": 84, "الانشقاق": 84,
    "buruj": 85, "البروج": 85,
    "tariq": 86, "الطارق": 86,
    "ala": 87, "a'la": 87, "الأعلى": 87,
    "ghashiyah": 88, "الغاشية": 88,
    "fajr": 89, "fejr": 89, "الفجر": 89,
    "balad": 90, "البلد": 90,
    # 91-100
    "shams": 91, "شمس": 91, "الشمس": 91,
    "layl": 92, "leyl": 92, "الليل": 92,
    "duha": 93, "dhuha": 93, "الضحى": 93,
    "sharh": 94, "inshirah": 94, "الشرح": 94,
    "tin": 95, "التين": 95,
    "alaq": 96, "'alaq": 96, "العلق": 96,
    "qadr": 97, "kadir": 97, "القدر": 97,
    "bayyinah": 98, "البيّنة": 98, "البينة": 98,
    "zalzalah": 99, "zilzal": 99, "الزلزلة": 99,
    "adiyat": 100, "'adiyat": 100, "العاديات": 100,
    # 101-114
    "qariah": 101, "qari'ah": 101, "القارعة": 101,
    "takathur": 102, "التكاثر": 102,
    "asr": 103, "'asr": 103, "العصر": 103,
    "humazah": 104, "الهمزة": 104,
    "fil": 105, "feel": 105, "الفيل": 105,
    "quraysh": 106, "quraish": 106, "قريش": 106,
    "maun": 107, "ma'un": 107, "الماعون": 107,
    "kawthar": 108, "kautsar": 108, "kevser": 108, "الكوثر": 108,
    "kafirun": 109, "kafiroon": 109, "الكافرون": 109,
    "nasr": 110, "النصر": 110,
    "masad": 111, "lahab": 111, "المسد": 111,
    "ikhlas": 112, "ihlas": 112, "الإخلاص": 112,
    "falaq": 113, "felak": 113, "الفلق": 113,
    "nas": 114, "naas": 114, "الناس": 114
}

SURAH_OFFICIAL_NAMES = [
    "", "Al-Fatihah", "Al-Baqarah", "Ali 'Imran", "An-Nisa'", "Al-Ma'idah", "Al-An'am", "Al-A'raf", "Al-Anfal", "At-Tawbah",
    "Yunus", "Hud", "Yusuf", "Ar-Ra'd", "Ibrahim", "Al-Hijr", "An-Nahl", "Al-Isra'", "Al-Kahf", "Maryam",
    "Ta-Ha", "Al-Anbiya'", "Al-Hajj", "Al-Mu'minun", "An-Nur", "Al-Furqan", "Ash-Shu'ara'", "An-Naml", "Al-Qasas", "Al-'Ankabut",
    "Ar-Rum", "Luqman", "As-Sajdah", "Al-Ahzab", "Saba'", "Fatir", "Ya-Sin", "As-Saffat", "Sad", "Az-Zumar",
    "Ghafir", "Fussilat", "Ash-Shura", "Az-Zukhruf", "Ad-Dukhan", "Al-Jathiyah", "Al-Ahqaf", "Muhammad", "Al-Fath", "Al-Hujurat",
    "Qaf", "Adh-Dhariyat", "At-Tur", "An-Najm", "Al-Qamar", "Ar-Rahman", "Al-Waqi'ah", "Al-Hadid", "Al-Mujadila", "Al-Hashr",
    "Al-Mumtahanah", "As-Saff", "Al-Jumu'ah", "Al-Munafiqun", "At-Taghabun", "At-Talaq", "At-Tahrim", "Al-Mulk", "Al-Qalam", "Al-Haqqah",
    "Al-Ma'arij", "Nuh", "Al-Jinn", "Al-Muzzammil", "Al-Muddaththir", "Al-Qiyamah", "Al-Insan", "Al-Mursalat", "An-Naba'", "An-Nazi'at",
    "'Abasa", "At-Takwir", "Al-Infitar", "Al-Mutaffifin", "Al-Inshiqaq", "Al-Buruj", "At-Tariq", "Al-A'la", "Al-Ghashiyah", "Al-Fajr",
    "Al-Balad", "Ash-Shams", "Al-Layl", "Ad-Duha", "Ash-Sharh", "At-Tin", "Al-'Alaq", "Al-Qadr", "Al-Bayyinah", "Az-Zalzalah",
    "Al-'Adiyat", "Al-Qari'ah", "At-Takathur", "Al-'Asr", "Al-Humazah", "Al-Fil", "Quraysh", "Al-Ma'un", "Al-Kawthar", "Al-Kafirun",
    "An-Nasr", "Al-Masad", "Al-Ikhlas", "Al-Falaq", "An-Nas"
]

class QuranDatabase:
    def __init__(self, arabic_path: str = CONFIG.HAFS_JSON_PATH, translation_path: str = CONFIG.ENGLISH_WBW_PATH):
        self.arabic_path = arabic_path
        self.translation_path = translation_path
        self.arabic_data: Dict[str, Dict[str, str]] = {}
        self.translation_data: Dict[str, Dict[str, str]] = {}
        self.is_loaded: bool = False

    def load_data(self) -> bool:
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
        parsed: Dict[str, Dict[str, str]] = {}
        if isinstance(raw_data, dict):
            for key, val in raw_data.items():
                surah, ayah = "", ""
                if ":" in key:
                    surah, ayah = key.split(":", 1)
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
        s_key, a_key = str(surah_num), str(ayah_num)
        ar_text = self.arabic_data.get(s_key, {}).get(a_key, "")
        tr_text = self.translation_data.get(s_key, {}).get(a_key, "")
        
        if ar_text or tr_text:
            s_official = SURAH_OFFICIAL_NAMES[surah_num] if 1 <= surah_num <= 114 else f"Surah {surah_num}"
            return {
                "surah_name": s_official,
                "surah_num": surah_num,
                "ayah_num": ayah_num,
                "ar": ar_text,
                "tr": tr_text
            }
        return None

    def get_range(self, surah_num: int, start_ayah: int, end_ayah: int) -> List[Dict[str, Any]]:
        return [v for a in range(start_ayah, end_ayah + 1) if (v := self.get_verse(surah_num, a))]

    @staticmethod
    def parse_verse_key(text: str) -> Optional[Tuple[int, int, Optional[int]]]:
        if not text:
            return None
            
        match_num = re.search(r'\b(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\b', text)
        if match_num:
            surah = int(match_num.group(1))
            start_a = int(match_num.group(2))
            end_a = int(match_num.group(3)) if match_num.group(3) else None
            if 1 <= surah <= 114:
                return surah, start_a, end_a

        clean_text = text.lower()
        clean_text = re.sub(r'\b(surah|sourate|sura|suresi|chapter|qs|qur\'an|quran|ayat|verse|سورة|سوره)\b', '', clean_text)
        match_name = re.search(r'([a-z\'\-\u0600-\u06FF\s]+)\s*[:\s]\s*(\d{1,3})(?:\s*-\s*(\d{1,3}))?', clean_text)
        
        if match_name:
            raw_s_name = match_name.group(1).strip()
            start_a = int(match_name.group(2))
            end_a = int(match_name.group(3)) if match_name.group(3) else None
            normalized_name = re.sub(r'^(al|an|ash|at|az|ar|ad|el|el-)\-?', '', raw_s_name).strip()
            
            if raw_s_name in SURAH_MAP:
                return SURAH_MAP[raw_s_name], start_a, end_a
            elif normalized_name in SURAH_MAP:
                return SURAH_MAP[normalized_name], start_a, end_a
                
        return None

QURAN_DB = QuranDatabase()
