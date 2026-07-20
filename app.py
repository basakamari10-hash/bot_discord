import streamlit as st
import subprocess
import sys
import os

st.set_page_config(page_title="Discord Bot Hub 24/7", page_icon="🤖")

st.title("🤖 Discord Multi-Bot Host 24/7")
st.write("Aplikasi ini menjalankan Bot Persona dan Bot Quran secara bersamaan.")

# 1. Salin Secrets Streamlit ke Environment Variables sistem
try:
    for key, value in st.secrets.items():
        os.environ[str(key)] = str(value)
except Exception as e:
    st.warning(f"Peringatan Secrets: {e}")

# 2. @st.cache_resource MEMASTIKAN bot HANYA di-spawn 1 KALI saja secara GLOBAL
#    (Mencegah bot membalas double / spam di Discord saat web di-refresh)
@st.cache_resource
def start_bots():
    print("🚀 Memulai subprocess Bot Persona...")
    p1 = subprocess.Popen([sys.executable, "bot_persona.py"])
    
    print("🚀 Memulai subprocess Bot Quran...")
    p2 = subprocess.Popen([sys.executable, "bot_quran.py"])
    
    return p1, p2

# Jalankan proses pemicu bot
bot_persona_proc, bot_quran_proc = start_bots()

st.success("✅ Both Bot Persona & Bot Quran are Online!")
st.info("🟢 Server Status: Active & Listening to Discord Events")
