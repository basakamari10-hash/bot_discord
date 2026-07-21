import streamlit as st
import subprocess
import sys
import os

st.set_page_config(page_title="Discord Bot Hub 24/7", page_icon="🤖")

st.title("🤖 Discord Multi-Bot Host 24/7")
st.write("Aplikasi ini menjalankan Bot Persona (Shion) dan Bot Quran secara bersamaan.")

# 1. Salin Secrets Streamlit ke Environment Variables sistem
try:
    for key, value in st.secrets.items():
        os.environ[str(key)] = str(value)
except Exception as e:
    st.warning(f"Peringatan Secrets: {e}")

# 2. Spawn Subprocess 1 Kali Secara Global
@st.cache_resource
def start_bots():
    print("🚀 Memulai subprocess Bot Persona (Shion)...")
    p1 = subprocess.Popen([sys.executable, "bot_persona.py"])
    
    print("🚀 Memulai subprocess Bot Quran...")
    p2 = subprocess.Popen([sys.executable, "bot_quran.py"])
    
    return p1, p2

# Jalankan proses pemicu bot
bot_persona_proc, bot_quran_proc = start_bots()

# 3. Pengecekan Status Real-Time di Dashboard Streamlit
st.subheader("📊 Status Proses Subprocess:")

col1, col2 = st.columns(2)

with col1:
    if bot_persona_proc.poll() is None:
        st.success("🟢 **Bot Persona (Shion)**: Running (PID: {})".format(bot_persona_proc.pid))
    else:
        st.error(f"🔴 **Bot Persona**: Stopped (Exit Code: {bot_persona_proc.poll()})")

with col2:
    if bot_quran_proc.poll() is None:
        st.success("🟢 **Bot Quran**: Running (PID: {})".format(bot_quran_proc.pid))
    else:
        st.error(f"🔴 **Bot Quran**: Stopped (Exit Code: {bot_quran_proc.poll()})")

st.info("💡 **Tips:** Jika salah satu bot mati, kamu cukup tekan tombol **Rerun / Reboot App** di Streamlit Cloud.")
