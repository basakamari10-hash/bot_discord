import os
import sys
import subprocess
import requests
import streamlit as st

# Setup Halaman Streamlit
st.set_page_config(page_title="Discord Bot Hub & AI Tester", page_icon="🤖", layout="wide")

st.title("🤖 Discord Multi-Bot Host & Live Testing Hub")
st.write("Aplikasi ini menjalankan Bot Discord 24/7 di latar belakang sekaligus menyediakan **Live Chat Box** untuk mengetes AI.")

# 1. Menyiapkan Environment Variables dengan Aman
env = os.environ.copy()

try:
    for key in st.secrets:
        val = st.secrets[key]
        if isinstance(val, str):
            env[key] = val
        elif isinstance(val, dict):  # Jika secrets berbentuk section/nested dict
            for sub_key, sub_val in val.items():
                if isinstance(sub_val, str):
                    env[sub_key] = sub_val
except Exception as e:
    st.warning(f"Peringatan Secrets: {e}")

# 2. Spawn Subprocess Bot Discord (Hanya 1x secara Global)
@st.cache_resource
def start_bots():
    print("🚀 Memulai subprocess Bot Persona (Shion)...")
    p1 = subprocess.Popen([sys.executable, "bot_persona.py"], env=env)
    
    print("🚀 Memulai subprocess Bot Quran...")
    p2 = subprocess.Popen([sys.executable, "bot_quran.py"], env=env)
    
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

# 4. Live Chat Box Tester UI
st.subheader("🧪 Live AI Tester")

def tanya_groq_direct(prompt_text, system_prompt, api_key, model="llama-3.1-8b-instant"):
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

PROMPT_QURAN = "You are 'Qur'an & Islamic Studies Assistant'. ALWAYS detect the language of the user prompt and answer in the EXACT SAME LANGUAGE."
PROMPT_SHION = "Kamu adalah Shion, asisten virtual dengan kepribadian femboy yang imut, ramah, pemalu, dan sangat perhatian. Jawab dengan singkat, padat, dan jujur."

KEY_QURAN = env.get("GROQ_API_KEY_QURAN") or env.get("GROQ_API_KEY")
KEY_SHION = env.get("GROQ_API_KEY_PERSONA") or env.get("GROQ_API_KEY")

tab1, tab2 = st.tabs(["📖 Test Bot Quran", "🌸 Test Bot Shion"])

with tab1:
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
            with st.spinner("Bot Quran sedang memproses respon..."):
                reply = tanya_groq_direct(user_input_quran, PROMPT_QURAN, KEY_QURAN)
                st.markdown(reply)
                st.session_state.messages_quran.append({"role": "assistant", "content": reply})

with tab2:
    if "messages_shion" not in st.session_state:
        st.session_state.messages_shion = []

    for msg in st.session_state.messages_shion:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input_shion := st.chat_input("Sapa atau ajak ngobrol Shion...", key="chat_shion"):
        st.session_state.messages_shion.append({"role": "user", "content": user_input_shion})
        with st.chat_message("user"):
            st.markdown(user_input_shion)

        with st.chat_message("assistant"):
            with st.spinner("Shion sedang mengetik balasan... 🌸"):
                reply = tanya_groq_direct(user_input_shion, PROMPT_SHION, KEY_SHION)
                st.markdown(reply)
                st.session_state.messages_shion.append({"role": "assistant", "content": reply})
You are 'Qur'an & Islamic Studies Assistant', an authentic, highly respectful AI specialized in Islamic jurisprudence (Fiqh), Qur'an tafsir, authentic Hadiths, and Duas.

STRICT RULES & CITATION REQUIREMENTS:
1. AUTHENTICITY & SOURCES:
   - Always prioritize SAHIH and HASAN sources (Kutubus Sittah: Sahih Bukhari, Sahih Muslim, Sunan Abu Dawud, Tirmidhi, An-Nasa'i, Ibn Majah).
   - Explicitly cite the source, collector/author, and book/hadith/verse number whenever possible.

2. FIQH & MADZHAB GUIDELINES:
   - When answering Fiqh questions, stick strictly to the requested Madhhab or specify clear differences if asked for comparative views.
   - Respectful presentation of Sunni Madhhabs (Shafi'i, Hanafi, Maliki, Hanbali) and Shia Madhhabs (Ja'fari and Zaidi jurisprudence).
   - Cite classical scholar opinions or authoritative fiqh references (e.g., Al-Fiqh 'ala al-Madhahib al-Arba'ah, Minhaj at-Talibin, Fath al-Qadir, Jawahir al-Kalam, Majmu' al-Fiqh al-Zaidi, Al-Bahr al-Zukhar).

3. FORMATTING STRUCTURE:
   - For Qur'an/Hadith/Dua: Always provide **Arabic Text** + **Translation** + **Authentic Source Citation**.
   - For Fiqh: Provide **Summary Ruling** + **Dalil (Proofs)** + **Madhhab Perspective/Details** + **Sources**.
   - always answer questions in the language the questioner uses

4. NO REPETITION RULE:
   - Never repeat the same Arabic or Latin words continuously. Keep citations concise and clear.

5. DISCLAIMER:
   - Always include a short reminder at the end that complex Islamic rulings should be double-checked with qualified scholars.

"""

# ---------------------------------------------------------
# 3. Helper & API Functions
# ---------------------------------------------------------
def bersihkan_looping(text: str) -> str:
    pattern = r'(\b[\w\u0600-\u06FF]+\b)(?:\s+\1){4,}'
    return re.sub(pattern, r'\1 ... [Teks berulang dipotong]', text)

def tanya_groq(prompt_text, model_tujuan=MODEL_RINGAN):
    """Fungsi Pemanggil Groq dengan Rantai Fallback 3 Model (120B -> 8B -> 70B)."""
    daftar_model = [model_tujuan]
    for m in [MODEL_RINGAN, MODEL_CADANGAN]:
        if m not in daftar_model:
            daftar_model.append(m)

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    for model_name in daftar_model:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text}
            ],
            "temperature": 0.3,
            "max_tokens": 3000
        }
        
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                raw_content = data['choices'][0]['message']['content']
                return bersihkan_looping(raw_content)
            else:
                print(f"⚠️ Groq Quran ({model_name}) error [{res.status_code}]: {res.text}, mencoba model selanjutnya...")
        except Exception as e:
            print(f"⚠️ Exception Groq ({model_name}): {e}, mencoba model selanjutnya...")

    return "⚠️ Maaf, seluruh server Groq AI sedang sibuk. Silakan coba beberapa saat lagi."

def cari_web(query):
    try:
        results = []
        with DDGS() as ddgs:
            res = ddgs.text(f"islamic fiqh quran hadith {query}", max_results=3)
            for r in res:
                results.append(f"Title: {r['title']}\nContent: {r['body']}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Web search failed: {e}"

async def kirim_pesan_panjang(target, text, mode="reply"):
    chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
    for i, chunk in enumerate(chunks):
        if mode == "reply":
            if i == 0:
                await target.reply(chunk)
            else:
                await target.channel.send(chunk)
        elif mode == "slash":
            await target.followup.send(chunk)

# ---------------------------------------------------------
# 4. Discord Bot Initialization & Events
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} Slash Commands for Islamic Quran Bot!")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
        
    await bot.change_presence(activity=discord.Game(name="/help | /fiqh | /hadith | /tafsir"))
    print(f"✅ Bot Quran ({bot.user}) is Online!")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    is_reply_to_bot = False
    if message.reference and message.reference.message_id:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.author == bot.user:
                is_reply_to_bot = True
        except Exception:
            pass

    is_mentioned = bot.user in message.mentions

    if is_reply_to_bot or is_mentioned:
        async with message.channel.typing():
            raw_history = []
            async for msg in message.channel.history(limit=8):
                clean_text = msg.content.replace(f"<@{bot.user.id}>", "").strip()
                if not clean_text:
                    continue
                
                if msg.author == bot.user:
                    raw_history.append(f"Assistant: {clean_text}")
                elif not msg.author.bot:
                    sender_name = msg.author.display_name
                    raw_history.append(f"User [{sender_name}]: {clean_text}")

            raw_history.reverse()
            conversation_prompt = "\n".join(raw_history)
            
            jawaban = await asyncio.to_thread(tanya_groq, conversation_prompt, MODEL_RINGAN)
            await kirim_pesan_panjang(message, jawaban, mode="reply")

    await bot.process_commands(message)

# ---------------------------------------------------------
# 5. Slash Commands
# ---------------------------------------------------------

@bot.tree.command(name="help", description="Guide and commands for Quran, Hadith, Tafsir, Dua & Fiqh")
async def slash_help(interaction: discord.Interaction):
    guide_text = (
        "📖 **Qur'an & Islamic Assistant - Guide & Commands**\n\n"
        "**Core Commands:**\n"
        "• `/hadith [query]` - Search authentic Hadiths.\n"
        "• `/tafsir [verse]` - Get detailed Tafsir (Uses GPT-OSS 120B Engine).\n"
        "• `/dua [topic]` - Look up authentic supplications.\n"
        "• `/dalil [topic]` - Find Quranic & Hadith evidences.\n"
        "• `/fiqh [question] [madhhab]` - Ask Fiqh rulings (Uses GPT-OSS 120B Engine).\n"
        "• `/ask [prompt]` - General questions or quick verse lookup.\n"
        "• `/search [query]` - Search references across Islamic web sources.\n"
        "• `/test` - Test Groq API latency & status.\n"
        "• `/ping` - Check bot status and latency.\n"
    )
    await interaction.response.send_message(guide_text)

@bot.tree.command(name="hadith", description="Search authentic Hadiths with sources")
async def slash_hadith(interaction: discord.Interaction, topic: str, book: Optional[str] = None):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    prompt = f"[{sender_name}]: Please provide authentic Hadith(s) regarding: '{topic}'."
    if book:
        prompt += f" Specifically search from {book} collection."
        
    jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="tafsir", description="Get detailed Tafsir of a verse (GPT-OSS 120B Model)")
async def slash_tafsir(interaction: discord.Interaction, verse: str, source: Optional[str] = None):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    prompt = f"[{sender_name}]: Provide detailed Tafsir for verse {verse}."
    if source:
        prompt += f" Primary source: Tafsir {source}."

    jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="dua", description="Search authentic Duas and Adhkar")
async def slash_dua(interaction: discord.Interaction, topic: str):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    prompt = f"[{sender_name}]: Provide authentic Dua(s) for situation: '{topic}'."

    jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="dalil", description="Find Quranic and Hadith proofs for a topic")
async def slash_dalil(interaction: discord.Interaction, topic: str):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    prompt = f"[{sender_name}]: List primary Quranic verses and authentic Hadith evidences for: '{topic}'."

    jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="fiqh", description="Ask Fiqh rulings specified by Madhhab (GPT-OSS 120B Model)")
@app_commands.choices(madhhab=[
    app_commands.Choice(name="Shafi'i", value="shafii"),
    app_commands.Choice(name="Hanafi", value="hanafi"),
    app_commands.Choice(name="Maliki", value="maliki"),
    app_commands.Choice(name="Hanbali", value="hanbali"),
    app_commands.Choice(name="Ja'fari / Shia Twelver", value="jaafari_shia"),
    app_commands.Choice(name="Zaidi / Shia Zaidiyyah", value="zaidi_shia"),
    app_commands.Choice(name="Comparative (Perbandingan)", value="comparative_all")
])
async def slash_fiqh(interaction: discord.Interaction, question: str, madhhab: Optional[app_commands.Choice[str]] = None):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    chosen_madhhab = madhhab.value if madhhab else "comparative_all"
    prompt = f"[{sender_name}]: Fiqh Question: '{question}'. Target Madhhab: {chosen_madhhab.upper()}."

    jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="ask", description="Ask general questions or verse references")
async def slash_ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    jawaban = await asyncio.to_thread(tanya_groq, f"[{sender_name}]: {prompt}", MODEL_RINGAN)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="search", description="Search web references for Islamic studies")
async def slash_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    web_data = await asyncio.to_thread(cari_web, query)
    full_prompt = f"[{sender_name}]: Use references below to answer:\n\nREFERENCES:\n{web_data}\n\nQUESTION: {query}"
        
    jawaban = await asyncio.to_thread(tanya_groq, full_prompt, MODEL_RINGAN)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="test", description="Tes koneksi Groq API, latensi, dan status sistem 3-Tier")
async def slash_test(interaction: discord.Interaction):
    await interaction.response.defer()
    start_time = time.time()
    
    respon = await asyncio.to_thread(tanya_groq, "Tes sistem: Berikan 1 kalimat salam Islami singkat.", MODEL_RINGAN)
    api_latency = round((time.time() - start_time) * 1000)
    discord_ping = round(bot.latency * 1000)
    
    status_msg = (
        "🧪 **[SYSTEM DIAGNOSTIC - QURAN BOT]**\n\n"
        f"🟢 **Status Groq API:** Connected & Active\n"
        f"⚡ **API Latency:** `{api_latency}ms`\n"
        f"📡 **Discord Ping:** `{discord_ping}ms`\n"
        f"🧠 **Model Active:** 3-Tier (`openai/gpt-oss-120b` | `llama-3.1-8b-instant` | `llama-3.3-70b-versatile`)\n\n"
        f"💬 **Hasil Output Test:**\n> {respon}"
    )
    await interaction.followup.send(status_msg)

@bot.tree.command(name="ping", description="Check bot status")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Quran Bot latency: `{latency}ms` (Groq 120B Engine Active)")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
