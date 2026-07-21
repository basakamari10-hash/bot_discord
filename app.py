import streamlit as st
import subprocess
import sys
import os

st.set_page_config(page_title="Discord Bot Hub 24/7", page_icon="🤖")

st.title("🤖 Discord Multi-Bot Host 24/7")
st.write("Aplikasi ini menjalankan Bot Persona (Shion) dan Bot Quran secara bersamaan menggunakan Groq AI Engine.")

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
    print("🚀 Memulai subprocess Bot Persona (Shion)...")
    p1 = subprocess.Popen([sys.executable, "bot_persona.py"])
    
    print("🚀 Memulai subprocess Bot Quran...")
    p2 = subprocess.Popen([sys.executable, "bot_quran.py"])
    
    return p1, p2

# Jalankan proses pemicu bot
bot_persona_proc, bot_quran_proc = start_bots()

# 3. Status Process Monitoring
st.subheader("📊 Status Subprocess Bot Real-Time:")

col1, col2 = st.columns(2)

with col1:
    if bot_persona_proc.poll() is None:
        st.success(f"🟢 **Bot Persona (Shion)**: Running (PID: {bot_persona_proc.pid})")
    else:
        st.error(f"🔴 **Bot Persona**: Stopped (Exit Code: {bot_persona_proc.poll()})")

with col2:
    if bot_quran_proc.poll() is None:
        st.success(f"🟢 **Bot Quran**: Running (PID: {bot_quran_proc.pid})")
    else:
        st.error(f"🔴 **Bot Quran**: Stopped (Exit Code: {bot_quran_proc.poll()})")

st.info("💡 **Tips:** Jika salah satu bot mati/terhenti, kamu cukup tekan tombol **Reboot / Rerun App** di Streamlit Cloud.")
