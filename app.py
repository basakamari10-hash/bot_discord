import streamlit as st
import subprocess
import sys
import threading
import os

st.set_page_config(page_title="Discord Bot Manager", page_icon="🤖")

st.title("🤖 Discord Bot Host 24/7")
st.write("Aplikasi ini menjalankan Bot Persona dan Bot Quran secara otomatis.")

# Salin Secrets Streamlit ke Environment Variables sistem
try:
    for key, value in st.secrets.items():
        os.environ[key] = str(value)
except Exception:
    pass

def run_bots():
    # Jalankan kedua skrip bot di background
    p1 = subprocess.Popen([sys.executable, "bot_persona.py"])
    p2 = subprocess.Popen([sys.executable, "bot_quran.py"])
    p1.wait()
    p2.wait()

# Jalankan thread bot hanya sekali saat aplikasi dinyalakan
if "bot_started" not in st.session_state:
    st.session_state["bot_started"] = True
    threading.Thread(target=run_bots, daemon=True).start()
    st.success("✅ Bot Persona & Bot Quran berhasil dijalankan di latar belakang!")

st.info("🟢 Status Server: Online & Running")