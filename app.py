import os
import sys
import subprocess
import requests
import streamlit as st

# Setup Halaman Streamlit
st.set_page_config(page_title="Islamic AI Bot Hub", page_icon="🕌", layout="wide")

st.title("🕌 Islamic AI Bot Host & Live Testing Hub")
st.write("Aplikasi ini menjalankan Bot Discord Islamic AI 24/7 di latar belakang sekaligus menyediakan **Live Chat Box** untuk pengetesan.")

# ---------------------------------------------------------
# 1. Definisi Variabel Global & Prompt
# ---------------------------------------------------------
MODEL_TESTER = "llama-3.1-8b-instant"

PROMPT_QURAN = (
    "You are 'Qur'an & Islamic Studies Assistant', an authentic, highly respectful AI specialized in Islamic jurisprudence (Fiqh), "
    "Qur'an tafsir, authentic Hadiths, and Duas. ALWAYS detect the language of the user prompt and answer in the EXACT SAME LANGUAGE."
)

# ---------------------------------------------------------
# 2. Menyiapkan Environment Variables dengan Aman
# ---------------------------------------------------------
env = os.environ.copy()

try:
    for key in st.secrets:
        val = st.secrets[key]
        if isinstance(val, str):
            env[key] = val
        elif isinstance(val, dict):
            for sub_key, sub_val in val.items():
                if isinstance(sub_val, str):
                    env[sub_key] = sub_val
except Exception as e:
    st.warning(f"Peringatan Secrets: {e}")

# Ambil API Key Groq dari Environment
KEY_QURAN = env.get("GROQ_API_KEY_QURAN") or env.get("GROQ_API_KEY")

# ---------------------------------------------------------
# 3. Spawn Subprocess Bot Discord (Hanya 1x secara Global)
# ---------------------------------------------------------
@st.cache_resource
def start_bots():
    print("🚀 Memulai subprocess Bot Islamic AI...")
    # Pastikan file bot_quran.py ada di folder yang sama
    p_quran = subprocess.Popen([sys.executable, "bot_quran.py"], env=env)
    return p_quran

bot_quran_proc = start_bots()

# ---------------------------------------------------------
# 4. Status Monitoring Process
# ---------------------------------------------------------
st.subheader("📊 Status Server Discord Bot:")

if bot_quran_proc.poll() is None:
    st.success(f"🟢 **Bot Islamic AI**: Running (PID: {bot_quran_proc.pid})")
else:
    st.error(f"🔴 **Bot Islamic AI**: Stopped (Exit Code: {bot_quran_proc.poll()})")

st.divider()

# ---------------------------------------------------------
# 5. Fungsi Pemanggil API untuk Web Chat Tester
# ---------------------------------------------------------
def tanya_groq_direct(prompt_text, system_prompt, api_key, model=MODEL_TESTER):
    if not api_key:
        return "❌ Error: GROQ_API_KEY belum diisi di Environment atau Streamlit Secrets!"
    
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

# ---------------------------------------------------------
# 6. Live Chat Box Tester UI
# ---------------------------------------------------------
st.subheader("🧪 Live AI Tester - Islamic Assistant")

if "messages_quran" not in st.session_state:
    st.session_state.messages_quran = []

for msg in st.session_state.messages_quran:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input_quran := st.chat_input("Tanya seputar Al-Qur'an, Hadits, atau Fiqh...", key="chat_quran"):
    st.session_state.messages_quran.append({"role": "user", "content": user_input_quran})
    with st.chat_message("user"):
        st.markdown(user_input_quran)

    with st.chat_message("assistant"):
        with st.spinner("Islamic AI sedang memproses respon... 🕌"):
            reply = tanya_groq_direct(user_input_quran, PROMPT_QURAN, KEY_QURAN)
            st.markdown(reply)
            st.session_state.messages_quran.append({"role": "assistant", "content": reply})
