import streamlit as st
import subprocess
import sys
import os

st.set_page_config(page_title="Discord Bot Manager", page_icon="🤖")

st.title("🤖 Discord Bot Host 24/7")
st.write("Aplikasi ini menjalankan Bot Persona dan Bot Quran secara otomatis.")

# 1. Salin Secrets Streamlit ke Environment Variables sistem
try:
    for key, value in st.secrets.items():
        os.environ[str(key)] = str(value)
except Exception as e:
    st.warning(f"Sistem Secrets: {e}")

# 2. Pakai @st.cache_resource agar bot HANYA berjalan 1x secara GLOBAL
# (Tidak akan pernah jalan berulang kali meskipun web di-refresh)
@st.cache_resource
def start_discord_bots():
    p1 = subprocess.Popen([sys.executable, "bot_persona.py"])
    p2 = subprocess.Popen([sys.executable, "bot_quran.py"])
    return p1, p2

# Jalankan proses pemicu bot
bot_processes = start_discord_bots()

st.success("✅ Bot Persona & Bot Quran berhasil dijalankan di latar belakang (Global Single-Instance)!")
st.info("🟢 Status Server: Online & Running")
