import os
import re
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import requests
import streamlit as st
from duckduckgo_search import DDGS
from typing import Optional

# ---------------------------------------------------------
# 1. Streamlit Dashboard Setup
# ---------------------------------------------------------
st.set_page_config(page_title="Bot Quran Discord", page_icon="📖")
st.title("📖 Bot Quran & Islamic Assistant 24/7")
st.success("🟢 Bot Quran Server (Google AI Studio Direct API Active)!")

# ---------------------------------------------------------
# 2. Token & API Configuration
# ---------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_QURAN") or st.secrets.get("DISCORD_TOKEN_QURAN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")

# Menggunakan Gemini 2.0 Flash untuk kecepatan dan akurasi tinggi
MODEL_NAME = "gemini-2.0-flash"

SYSTEM_PROMPT = """
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

4. NO REPETITION RULE:
   - Never repeat the same Arabic or Latin words continuously. Keep citations concise and clear.

5. DISCLAIMER:
   - Always include a short reminder at the end that complex Islamic rulings should be double-checked with qualified scholars.
"""

# ---------------------------------------------------------
# 3. Helper & API Functions
# ---------------------------------------------------------
def bersihkan_looping(text: str) -> str:
    """Memotong jika ada kata/frasa yang terulang lebih dari 4 kali berturut-turut."""
    pattern = r'(\b[\w\u0600-\u06FF]+\b)(?:\s+\1){4,}'
    return re.sub(pattern, r'\1 ... [Teks berulang dipotong otomatis]', text)

def tanya_gemini(prompt_text):
    """Memanggil API Resmi Google AI Studio (Direct Gemini API)"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": SYSTEM_PROMPT}
            ]
        },
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 3000
        }
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            data = res.json()
            raw_content = data['candidates'][0]['content']['parts'][0]['text']
            return bersihkan_looping(raw_content)
        else:
            return f"⚠️ Google Gemini API Error ({res.status_code}): {res.text}"
    except Exception as e:
        return f"⚠️ Connection Error: {e}"

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
    """Splits long responses (>1800 chars) into chunked messages."""
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
            
            jawaban = await asyncio.to_thread(tanya_gemini, conversation_prompt)
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
        "• `/hadith [query]` - Search authentic Hadiths with grading & book numbers.\n"
        "• `/tafsir [verse]` - Get detailed Tafsir with explicit sources (Ibn Kathir, Kemenag, etc.).\n"
        "• `/dua [topic]` - Look up authentic supplications with Arabic & translation.\n"
        "• `/dalil [topic]` - Find Quranic & Hadith evidences for a topic.\n"
        "• `/fiqh [question] [madhhab]` - Ask Fiqh rulings based on specific Madhhabs (Shafi'i, Hanafi, Maliki, Hanbali, Ja'fari, Zaidi, or Comparative).\n"
        "• `/ask [prompt]` - General questions or quick verse lookup (e.g., `1:1-7`).\n"
        "• `/search [query]` - Search references across Islamic web sources.\n"
        "• `/ping` - Check bot status and latency.\n\n"
        "⚠️ *All rulings cite authentic sources. Please consult local qualified scholars for personal fatwas.*"
    )
    await interaction.response.send_message(guide_text)

@bot.tree.command(name="hadith", description="Search authentic Hadiths (Bukhari, Muslim, etc.) with sources")
@app_commands.describe(
    topic="Topic or keywords of the Hadith",
    book="Optional: Specific collection (e.g., Bukhari, Muslim, Abu Dawud)"
)
async def slash_hadith(interaction: discord.Interaction, topic: str, book: Optional[str] = None):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    
    prompt = f"[{sender_name}]: Please provide authentic Hadith(s) regarding: '{topic}'."
    if book:
        prompt += f" Specifically search from {book} collection."
    prompt += " Include Arabic text, translation, collection name, hadith number, and authenticity status (Sahih/Hasan)."

    jawaban = await asyncio.to_thread(tanya_gemini, prompt)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="tafsir", description="Get detailed Tafsir of a verse with source citations")
@app_commands.describe(
    verse="Verse reference (e.g., '2:255', 'Al-Baqarah 255')",
    source="Optional: Tafsir book (e.g., 'Ibn Kathir', 'Al-Jalalayn', 'Kemenag RI')"
)
async def slash_tafsir(interaction: discord.Interaction, verse: str, source: Optional[str] = None):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    
    prompt = f"[{sender_name}]: Provide detailed Tafsir for verse {verse}."
    if source:
        prompt += f" Primary source: Tafsir {source}."
    prompt += " Mention verse Arabic text, translation, and explanation from verified Tafsir scholars."

    jawaban = await asyncio.to_thread(tanya_gemini, prompt)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="dua", description="Search authentic Duas and Adhkar with sources")
@app_commands.describe(
    topic="Topic or situation for the Dua (e.g., 'before sleep', 'for forgiveness', 'anxiety')"
)
async def slash_dua(interaction: discord.Interaction, topic: str):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    
    prompt = f"[{sender_name}]: Provide authentic Dua(s) for situation: '{topic}'. Include Arabic text, transliteration, translation, and reference source (e.g., Hisnul Muslim / Sahih Bukhari)."

    jawaban = await asyncio.to_thread(tanya_gemini, prompt)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="dalil", description="Find Quranic and Hadith proofs/evidences for a specific issue")
@app_commands.describe(
    topic="Topic or issue to search evidence for (e.g., 'patience in adversity', 'honoring parents')"
)
async def slash_dalil(interaction: discord.Interaction, topic: str):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    
    prompt = f"[{sender_name}]: List primary Quranic verses and authentic Hadith evidences (Dalil) for: '{topic}'. Cite exact Surah/Verse numbers and Hadith sources."

    jawaban = await asyncio.to_thread(tanya_gemini, prompt)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="fiqh", description="Ask Fiqh rulings specified by Madhhab or comparative views")
@app_commands.describe(
    question="Your Fiqh question",
    madhhab="Choose Madhhab or Comparative view"
)
@app_commands.choices(madhhab=[
    app_commands.Choice(name="Shafi'i (Madzhab Syafi'i)", value="shafii"),
    app_commands.Choice(name="Hanafi (Madzhab Hanafi)", value="hanafi"),
    app_commands.Choice(name="Maliki (Madzhab Maliki)", value="maliki"),
    app_commands.Choice(name="Hanbali (Madzhab Hanbali)", value="hanbali"),
    app_commands.Choice(name="Ja'fari / Shia Twelver (Madzhab Ja'fari)", value="jaafari_shia"),
    app_commands.Choice(name="Zaidi / Shia Zaidiyyah (Madzhab Zaidi)", value="zaidi_shia"),
    app_commands.Choice(name="Comparative (Semua Madzhab / Perbandingan)", value="comparative_all")
])
async def slash_fiqh(
    interaction: discord.Interaction, 
    question: str, 
    madhhab: Optional[app_commands.Choice[str]] = None
):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    
    chosen_madhhab = madhhab.value if madhhab else "comparative_all"
    
    prompt = (
        f"[{sender_name}]: Fiqh Question: '{question}'.\n"
        f"Target Madhhab Perspective: {chosen_madhhab.upper()}.\n"
        f"Please explain the ruling according to classical scholars of this Madhhab, "
        f"provide the Dalil (Quran/Hadith proofs), and cite authoritative Fiqh book references."
    )

    jawaban = await asyncio.to_thread(tanya_gemini, prompt)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="ask", description="Ask general questions or verse references (e.g. '1:1-7')")
@app_commands.describe(
    prompt="Enter prompt or verse number",
    language="Optional: Preferred response language (e.g. 'en', 'id', 'ar')"
)
async def slash_ask(interaction: discord.Interaction, prompt: str, language: Optional[str] = None):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    
    final_prompt = f"[{sender_name}]: {prompt}"
    if language:
        final_prompt += f"\n\n[Instruction: Reply in language '{language}']"
        
    jawaban = await asyncio.to_thread(tanya_gemini, final_prompt)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="search", description="Search web references for Islamic studies")
@app_commands.describe(
    query="Topic or keywords to search",
    language="Optional: Preferred response language"
)
async def slash_search(interaction: discord.Interaction, query: str, language: Optional[str] = None):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    
    web_data = await asyncio.to_thread(cari_web, query)
    full_prompt = f"[{sender_name}]: Use references below to answer:\n\nREFERENCES:\n{web_data}\n\nQUESTION: {query}"
    if language:
        full_prompt += f"\n\n[Instruction: Reply in language '{language}']"
        
    jawaban = await asyncio.to_thread(tanya_gemini, full_prompt)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="ping", description="Check bot latency and status")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Quran & Fiqh Bot latency: `{latency}ms`")

# ---------------------------------------------------------
# 6. Run Bot
# ---------------------------------------------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
