import json
import os
from typing import Tuple

# Daftar file tafsir dan nama tampilannya (Pastikan nama file sesuai dengan yang Anda miliki)
TAFSIR_FILES = {
    "tafsir-al-jalalayn.json": "Tafsir Al-Jalalayn",
    "en-tafisr-ibn-kathir.json": "Tafsir Ibn Kathir",
    "en-tafsir-maarif-ul-quran.json": "Tafsir Ma'ariful Qur'an"
}

def get_tafsir_with_fallback(verse_key: str, primary_file: str) -> Tuple[str, str, bool]:
    """
    Mengambil tafsir berdasarkan verse_key (misal '1:4').
    Returns: (teks_tafsir, nama_sumber_yang_digunakan, is_fallback)
    """
    # Susun urutan pencarian: File yang dipilih user dicek duluan, baru sisanya
    search_order = [primary_file] + [f for f in TAFSIR_FILES.keys() if f != primary_file]
    
    for file_name in search_order:
        if os.path.exists(file_name):
            try:
                with open(file_name, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # Cek apakah verse_key ada di file JSON dan isinya tidak kosong
                    if verse_key in data and data[verse_key].get("text"):
                        source_name = TAFSIR_FILES.get(file_name, file_name)
                        is_fallback = (file_name != primary_file)
                        
                        return data[verse_key]["text"], source_name, is_fallback
            except Exception as e:
                print(f"Error reading {file_name}: {e}")
                continue

    # Jika dicari ke semua file tetap tidak ada
    return "", "", False
