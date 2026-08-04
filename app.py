import os
import sys
import time
import subprocess
from datetime import datetime

import requests
import streamlit as st

# ===========================================================
# 1. KONFIGURASI HALAMAN & TEMA VISUAL
# ===========================================================
st.set_page_config(
    page_title="Islamic AI Bot Hub",
    page_icon="🕌",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
:root {
    --emerald: #0f5132;
    --emerald-light: #14804a;
    --gold: #d4af37;
    --cream: #fdfaf3;
}

/* Latar belakang umum */
.stApp {
    background: radial-gradient(circle at top left, #0b3d2e 0%, #05201a 45%, #04140f 100%);
}

/* Header hero */
.hero-banner {
    background: linear-gradient(135deg, var(--emerald) 0%, var(--emerald-light) 60%, #0b6e46 100%);
    border-radius: 18px;
    padding: 28px 32px;
    margin-bottom: 22px;
    box-shadow: 0 8px 28px rgba(0,0,0,0.35);
    border: 1px solid rgba(212,175,55,0.35);
    position: relative;
    overflow: hidden;
}
.hero-banner::after {
    content: "☪";
    position: absolute;
    right: 24px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 90px;
    opacity: 0.10;
    color: var(--gold);
}
.hero-title {
    font-size: 34px;
    font-weight: 800;
    color: var(--cream);
    margin: 0;
}
.hero-sub {
    color: rgba(253,250,243,0.85);
    font-size: 15px;
    margin-top: 6px;
}

/* Kartu status */
.status-card {
    border-radius: 14px;
    padding: 16px 20px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(212,175,55,0.25);
    backdrop-filter: blur(4px);
}
.status-online {
    border-left: 5px solid #2ecc71;
}
.status-offline {
    border-left: 5px solid #e74c3c;
}
.status-label {
    color: rgba(253,250,243,0.7);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.status-value {
    color: var(--cream);
    font-size: 18px;
    font-weight: 700;
    margin-top: 2px;
}

/* Quick prompt chips */
div[data-testid="stButton"] > button {
    border-radius: 999px !important;
    border: 1px solid rgba(212,175,55,0.5) !important;
    background: rgba(212,175,55,0.08) !important;
    color: var(--cream) !important;
    font-weight: 500 !important;
    transition: all 0.15s ease-in-out;
}
div[data-testid="stButton"] > button:hover {
    background: var(--gold) !important;
    color: #05201a !important;
    border-color: var(--gold) !important;
    transform: translateY(-1px);
}

/* Chat bubbles container spacing */
.chat-meta {
    font-size: 11px;
    color: rgba(253,250,243,0.5);
    margin-top: -6px;
    margin-bottom: 4px;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #05201a 0%, #0b3d2e 100%);
    border-right: 1px solid rgba(212,175,55,0.25);
}
section[data-testid="stSidebar"] * {
    color: var(--cream) !important;
}

h1, h2, h3, h4, p, label, span {
    color: var(--cream);
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ===========================================================
# 2. VARIABEL GLOBAL & PROMPT SISTEM
# ===========================================================
MODEL_OPTIONS = {
    "⚡ Llama 3.1 8B (Instant / Cepat)": "llama-3.1-8b-instant",
    "🧠 Llama 3.3 70B (Versatile / Mendalam)": "llama-3.3-70b-versatile",
}

PROMPT_QURAN = (
    "You are 'Qur'an & Islamic Studies Assistant', an authentic, highly respectful AI specialized in Islamic jurisprudence (Fiqh), "
    "Qur'an tafsir, authentic Hadiths, and Duas. ALWAYS detect the language of the user prompt and answer in the EXACT SAME LANGUAGE."
)

QUICK_PROMPTS = [
    "📿 Apa keutamaan membaca Al-Fatihah?",
    "🤲 Doa sebelum makan dan artinya",
    "🕋 Rukun-rukun haji",
    "🧕 Adab menuntut ilmu dalam Islam",
    "🌙 Amalan sunnah di malam Jumat",
]

# ===========================================================
# 3. ENVIRONMENT VARIABLES
# ===========================================================
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
    st.warning(f"⚠️ Peringatan Secrets: {e}")

KEY_QURAN = env.get("GROQ_API_KEY_QURAN") or env.get("GROQ_API_KEY")

# ===========================================================
# 4. SPAWN SUBPROCESS BOT DISCORD
# ===========================================================
@st.cache_resource
def start_bots():
    print("🚀 Memulai subprocess Bot Islamic AI (main.py)...")
    p_quran = subprocess.Popen([sys.executable, "main.py"], env=env)
    return p_quran

bot_quran_proc = start_bots()

# ===========================================================
# 5. FUNGSI PEMANGGIL API GROQ
# ===========================================================
def tanya_groq_direct(prompt_text, system_prompt, api_key, model, temperature=0.7):
    if not api_key:
        return "❌ Error: GROQ_API_KEY belum diisi di Environment atau Streamlit Secrets!"

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": temperature,
        "max_tokens": 1500,
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
        else:
            return f"❌ Error API [{res.status_code}]: {res.text}"
    except Exception as e:
        return f"❌ Exception: {e}"

# ===========================================================
# 6. SIDEBAR — PENGATURAN & INFO
# ===========================================================
with st.sidebar:
    st.markdown("### ⚙️ Pengaturan Chat")

    model_label = st.selectbox("Pilih Model AI", list(MODEL_OPTIONS.keys()), index=0)
    selected_model = MODEL_OPTIONS[model_label]

    temperature = st.slider(
        "🎨 Kreativitas Jawaban (temperature)",
        min_value=0.0, max_value=1.0, value=0.7, step=0.1,
        help="Nilai rendah = jawaban lebih presisi & konsisten. Nilai tinggi = lebih variatif.",
    )

    st.markdown("---")
    st.markdown("### 📊 Statistik Sesi")
    total_msgs = len(st.session_state.get("messages_quran", []))
    st.metric("Total Pesan", total_msgs)
    st.metric("Pertanyaan Diajukan", total_msgs // 2 if total_msgs else 0)

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🗑️ Hapus Chat", use_container_width=True):
            st.session_state.messages_quran = []
            st.rerun()
    with col_b:
        if total_msgs > 0:
            transcript = "\n\n".join(
                f"[{m['role'].upper()}] {m['content']}" for m in st.session_state.messages_quran
            )
            st.download_button(
                "⬇️ Unduh", data=transcript, file_name="riwayat_chat_islamic_ai.txt",
                use_container_width=True,
            )
        else:
            st.button("⬇️ Unduh", disabled=True, use_container_width=True)

    st.markdown("---")
    st.caption("🕌 **Islamic AI Bot Hub**")
    st.caption("Ditenagai oleh Groq API • Dibangun dengan Streamlit")

# ===========================================================
# 7. HERO BANNER
# ===========================================================
st.markdown(
    """
    <div class="hero-banner">
        <p class="hero-title">🕌 Islamic AI Bot Host & Live Testing Hub</p>
        <p class="hero-sub">Menjalankan Bot Discord Islamic AI 24/7 di latar belakang, sekaligus menyediakan
        <b>Live Chat Box</b> interaktif untuk pengetesan seputar Al-Qur'an, Hadits, Fiqh, dan Doa.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ===========================================================
# 8. STATUS MONITORING (KARTU)
# ===========================================================
st.subheader("📊 Status Server Discord Bot")

col1, col2, col3 = st.columns(3)

is_running = bot_quran_proc.poll() is None
with col1:
    status_class = "status-online" if is_running else "status-offline"
    status_text = "🟢 Running" if is_running else f"🔴 Stopped ({bot_quran_proc.poll()})"
    st.markdown(
        f"""<div class="status-card {status_class}">
                <div class="status-label">Status Bot</div>
                <div class="status-value">{status_text}</div>
            </div>""",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"""<div class="status-card">
                <div class="status-label">Process ID</div>
                <div class="status-value">PID {bot_quran_proc.pid}</div>
            </div>""",
        unsafe_allow_html=True,
    )
with col3:
    key_status = "✅ Terpasang" if KEY_QURAN else "❌ Belum Diatur"
    st.markdown(
        f"""<div class="status-card">
                <div class="status-label">Groq API Key</div>
                <div class="status-value">{key_status}</div>
            </div>""",
        unsafe_allow_html=True,
    )

st.divider()

# ===========================================================
# 9. LIVE CHAT TESTER
# ===========================================================
st.subheader("🧪 Live AI Tester — Islamic Assistant")
st.caption(f"Model aktif: **{model_label}**")

if "messages_quran" not in st.session_state:
    st.session_state.messages_quran = []

# --- Quick prompt chips ---
st.markdown("**💡 Coba tanya:**")
chip_cols = st.columns(len(QUICK_PROMPTS))
quick_clicked = None
for i, prompt in enumerate(QUICK_PROMPTS):
    with chip_cols[i]:
        if st.button(prompt, key=f"chip_{i}", use_container_width=True):
            quick_clicked = prompt

st.markdown("")

# --- Render riwayat chat ---
avatar_map = {"user": "🧑", "assistant": "🕌"}
for msg in st.session_state.messages_quran:
    with st.chat_message(msg["role"], avatar=avatar_map.get(msg["role"])):
        st.markdown(msg["content"])
        if "time" in msg:
            st.markdown(f"<div class='chat-meta'>{msg['time']}</div>", unsafe_allow_html=True)

# --- Input pengguna (manual atau chip) ---
user_input_quran = st.chat_input("Tanya seputar Al-Qur'an, Hadits, atau Fiqh...", key="chat_quran")
final_input = quick_clicked or user_input_quran

if final_input:
    now = datetime.now().strftime("%H:%M")
    st.session_state.messages_quran.append({"role": "user", "content": final_input, "time": now})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(final_input)
        st.markdown(f"<div class='chat-meta'>{now}</div>", unsafe_allow_html=True)

    with st.chat_message("assistant", avatar="🕌"):
        with st.spinner("Islamic AI sedang memproses respon... 🕌"):
            reply = tanya_groq_direct(
                final_input, PROMPT_QURAN, KEY_QURAN,
                model=selected_model, temperature=temperature,
            )
        placeholder = st.empty()
        typed = ""
        for ch in reply:
            typed += ch
            if len(typed) % 4 == 0:
                placeholder.markdown(typed + "▌")
        placeholder.markdown(reply)
        reply_time = datetime.now().strftime("%H:%M")
        st.markdown(f"<div class='chat-meta'>{reply_time}</div>", unsafe_allow_html=True)
        st.session_state.messages_quran.append(
            {"role": "assistant", "content": reply, "time": reply_time}
        )

    if quick_clicked:
        st.rerun()
