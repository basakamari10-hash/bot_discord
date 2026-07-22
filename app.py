import os
import sys
import subprocess
import requests
import streamlit as st

# Setup Halaman
st.set_page_config(page_title="Discord Bot Hub & AI Tester", page_icon="🤖", layout="wide")

st.title("🤖 Discord Multi-Bot Host & Live Testing Hub")
st.write("Aplikasi ini menjalankan Bot Discord 24/7 di latar belakang sekaligus menyediakan **Live Chat Box** untuk mengetes AI secara langsung.")

# 1. Salin Secrets Streamlit ke Environment Variables sistem
try:
    for key, value in st.secrets.items():
        os.environ[str(key)] = str(value)
except Exception as e:
    st.warning(f"Peringatan Secrets: {e}")

# 2. Spawn Subprocess Bot Discord (Hanya 1x secara Global)
@st.cache_resource
def start_bots():
    print("🚀 Memulai subprocess Bot Persona (Shion)...")
    p1 = subprocess.Popen([sys.executable, "bot_persona.py"])
    
    print("🚀 Memulai subprocess Bot Quran...")
    p2 = subprocess.Popen([sys.executable, "bot_quran.py"])
    
    return p1, p2

bot_persona_proc, bot_quran_proc = start_bots()

# 3. Status Monitoring Process
st.subheader("📊 Status Server Discord Bot:")
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

st.divider()

# ---------------------------------------------------------
# 4. Live Chat Box Tester UI
# ---------------------------------------------------------
st.subheader("🧪 Live AI Tester (Langsung dari Web)")
st.caption("Kamu bisa ngetes respon AI di bawah ini tanpa perlu nunggu atau panggil di Discord!")

def tanya_groq_direct(prompt_text, system_prompt, api_key, model="llama-3.1-8b-instant"):
    """Fungsi pemanggil Groq API ringan untuk Chat Box Streamlit."""
    if not api_key:
        return "❌ Error: API Key Groq belum disetting di Secrets Streamlit!"
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.7,
        "max_tokens": 1500
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            return res.json()['choices'][0]['message']['content']
        else:
            return f"❌ Error API [{res.status_code}]: {res.text}"
    except Exception as e:
        return f"❌ Exception: {e}"

# System Prompts & Keys
PROMPT_QURAN = "You are 'Qur'an & Islamic Studies Assistant', an authentic, highly respectful AI specialized in Islamic jurisprudence (Fiqh), Qur'an tafsir, authentic Hadiths, and Duas."
PROMPT_SHION = "Kamu adalah Shion, asisten virtual dengan kepribadian femboy yang imut, ramah, pemalu, dan sangat perhatian. Jawab dengan singkat, padat, dan jujur."

KEY_QURAN = os.getenv("GROQ_API_KEY_QURAN") or os.getenv("GROQ_API_KEY")
KEY_SHION = os.getenv("GROQ_API_KEY_PERSONA") or os.getenv("GROQ_API_KEY")

tab1, tab2 = st.tabs(["📖 Test Bot Quran", "🌸 Test Bot Shion"])

# TAB 1: BOT QURAN TESTER
with tab1:
    if "messages_quran" not in st.session_state:
        st.session_state.messages_quran = []

    # Tampilkan riwayat chat
    for msg in st.session_state.messages_quran:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input Chat
    if user_input_quran := st.chat_input("Tanya seputar Al-Qur'an, Hadits, atau Fiqh...", key="chat_quran"):
        st.session_state.messages_quran.append({"role": "user", "content": user_input_quran})
        with st.chat_message("user"):
            st.markdown(user_input_quran)

        with st.chat_message("assistant"):
            with st.spinner("Bot Quran sedang memproses respon..."):
                reply = tanya_groq_direct(user_input_quran, PROMPT_QURAN, KEY_QURAN)
                st.markdown(reply)
                st.session_state.messages_quran.append({"role": "assistant", "content": reply})

# TAB 2: BOT SHION TESTER
with tab2:
    if "messages_shion" not in st.session_state:
        st.session_state.messages_shion = []

    # Tampilkan riwayat chat
    for msg in st.session_state.messages_shion:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input Chat
    if user_input_shion := st.chat_input("Sapa atau ajak ngobrol Shion...", key="chat_shion"):
        st.session_state.messages_shion.append({"role": "user", "content": user_input_shion})
        with st.chat_message("user"):
            st.markdown(user_input_shion)

        with st.chat_message("assistant"):
            with st.spinner("Shion sedang mengetik balasan... 🌸"):
                reply = tanya_groq_direct(user_input_shion, PROMPT_SHION, KEY_SHION)
                st.markdown(reply)
                st.session_state.messages_shion.append({"role": "assistant", "content": reply})

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
