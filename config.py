import os
import streamlit as st
from dataclasses import dataclass, field

def _get_secret(key: str, default: str = "") -> str:
    if hasattr(st, "secrets"):
        try:
            # Cek jika ada format section [ISLAMICAPI] di secrets.toml
            if key == "ISLAMIC_API_KEY" and "ISLAMICAPI" in st.secrets:
                val = st.secrets["ISLAMICAPI"].get("API_KEY") or st.secrets["ISLAMICAPI"].get("ISLAMIC_API_KEY")
                if val:
                    return str(val)

            # Cek standar st.secrets.get()
            val = st.secrets.get(f"{key}_QURAN") or st.secrets.get(key)
            if val:
                return str(val)
        except Exception:
            pass
    return os.getenv(f"{key}_QURAN") or os.getenv(key) or default

@dataclass
class Config:
    DISCORD_TOKEN: str = field(default_factory=lambda: _get_secret("DISCORD_TOKEN"))
    GROQ_API_KEY: str = field(default_factory=lambda: _get_secret("GROQ_API_KEY"))
    STREAMLIT_URL: str = field(default_factory=lambda: _get_secret("STREAMLIT_URL", "https://your-app-name.streamlit.app"))
    HADITH_API_KEY: str = field(default_factory=lambda: _get_secret("HADITH_API_KEY"))
    # ⚠️ SUDAH DITAMBAHKAN KUNCI ISLAMIC_API_KEY DI SINI! ⚠️
    ISLAMIC_API_KEY: str = field(default_factory=lambda: _get_secret("ISLAMIC_API_KEY"))
    
    PORT: int = field(default_factory=lambda: int(os.getenv("PORT", "8080")))
    
    MODEL_HEAVY: str = "openai/gpt-oss-120b"
    MODEL_LIGHT: str = "llama-3.3-70b-versatile"
    MODEL_FALLBACK: str = "llama-3.1-8b-instant"
    
    GROQ_MODELS: list[str] = field(default_factory=lambda: [
        "openai/gpt-oss-120b",
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant"
    ])
    
    CACHE_TTL_GROQ: int = 86400
    CACHE_TTL_SEARCH: int = 43200
    
    USER_COOLDOWN_SECONDS: float = 3.0
    CONCURRENT_REQUESTS_LIMIT: int = 5
    MAX_RETRIES: int = 3
    REQUEST_TIMEOUT: float = 25.0
    
    HAFS_JSON_PATH: str = os.getenv("HAFS_JSON_PATH", "qpc-hafs.json")
    ENGLISH_WBW_PATH: str = os.getenv("ENGLISH_WBW_PATH", "english-wbw-translation.json")

CONFIG = Config()
