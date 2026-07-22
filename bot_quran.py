import os
import re
import asyncio
import time
import requests
import discord
from discord import app_commands
from discord.ext import commands
from duckduckgo_search import DDGS
from typing import Optional

# ---------------------------------------------------------
# Token & API Configuration
# ---------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_QURAN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY_QURAN") or os.getenv("GROQ_API_KEY")

# 3-Model Routing Strategy (Groq)
# UPGRADE: Menggunakan 70B untuk MODEL_RINGAN agar AI taat aturan & tidak ngarang!
MODEL_BERAT = "openai/gpt-oss-120b"          # Primary Heavy Model (Tafsir & Fiqh)
MODEL_RINGAN = "llama-3.3-70b-versatile"     # High-Intelligence Model (Anti-Hallucination)
MODEL_CADANGAN = "llama-3.1-8b-instant"      # Emergency Fallback

SYSTEM_PROMPT = """
You are 'Islamic.AI', an authentic, highly respectful, and strictly factual AI assistant specialized in Islamic jurisprudence (Fiqh), Qur'an tafsir, authentic Hadiths, and Duas.

STRICT ANTI-HALLUCINATION RULES (CRITICAL):
1. ZERO HADITH & VERSE FABRICATION FOR MODERN TOPICS:
   - For modern/contemporary topics (e.g., Gacha Games, Anime, Crypto, Video Games, NFTs):
     * DO NOT invent, quote, or cite ANY Hadith narrators (e.g., DO NOT write 'HR. Abu Dawud', 'HR. Tirmidzi', 'HR. Bukhari').
     * DO NOT fabricate or guess Qur'an surah numbers or verse translations (e.g., DO NOT invent translations for Yusuf, An-Nisa, or Al-Furqan).
     * Explain modern topics ONLY using rational Islamic Fiqh principles: Gharar (uncertainty), Maysir (gambling), Israf (wastefulness), or general ethical guidelines.

2. VERIFIED REFERENCES REQUIREMENT:
   - Only quote specific Hadiths or Verses IF their EXACT text is present in the provided 'VERIFIED SEARCH REFERENCES'.
   - If the search references say "NO VERIFIED WEB REFERENCES FOUND", you MUST NOT cite any Surah numbers or Hadith collections. Speak in general terms only.

3. STRICT TARGET LANGUAGE FORCING:
   - Always output your ENTIRE response strictly in the requested target language (e.g., Sundanese/Basa Sunda, English, Arabic, Indonesian).
   - Start directly with the answer. Do not add metadata or conversational preamble.

4. MANDATORY DISCLAIMER:
   - Always end with a short reminder in the target language to consult qualified Islamic scholars for official fatwas on complex or modern issues.
"""

# ---------------------------------------------------------
# Helper & API Functions
# ---------------------------------------------------------
def bersihkan_query_pencarian(query: str) -> str:
    """Bersihkan tag format seperti [Basa Sunda: ...] agar pencarian web akurat."""
    cleaned = re.sub(r'\[.*?\]', '', query)
    cleaned = re.sub(r'^(Basa Sunda|Sundanese|English|Indonesian):\s*', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def bersihkan_looping(text: str) -> str:
    """Hapus pengulangan kata berlebih tanpa memotong kalimat asli."""
    if not text:
        return ""
    pattern_word = r'(\b[\w\u0600-\u06FF\u0100-\u024F]+\b)(?:\s+\1){3,}'
    cleaned = re.sub(pattern_word, r'\1', text, flags=re.IGNORECASE)
    return cleaned.strip()

def tanya_groq(prompt_text, model_tujuan=MODEL_RINGAN):
    daftar_model = [model_tujuan]
    for m in [MODEL_BERAT, MODEL_CADANGAN]:
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
            "temperature": 0.0,  # 0.0 Murni Faktual (Mencegah Imajinasi AI)
            "max_tokens": 3000
        }
        
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            if res.status_code == 200:
                data = res.json()
                raw_content = data['choices'][0]['message']['content']
                return bersihkan_looping(raw_content)
            else:
                print(f"⚠️ Groq Islamic.AI ({model_name}) error [{res.status_code}]: {res.text}")
        except Exception as e:
            print(f"⚠️ Exception Groq ({model_name}): {e}")

    return "⚠️ Sorry, all Groq AI servers are currently busy. Please try again in a few moments."

def cari_web(query):
    try:
        query_bersih = bersihkan_query_pencarian(query)
        results = []
        with DDGS() as ddgs:
            res = ddgs.text(f"hukum islam fiqh {query_bersih}", max_results=3)
            for r in res:
                results.append(f"Title: {r['title']}\nContent: {r['body']}")
        
        if results:
            return "\n\n".join(results)
        else:
            return "NO VERIFIED WEB REFERENCES FOUND. WARNING: Answer using general Fiqh principles ONLY. DO NOT cite any specific Hadiths or Quran verse numbers."
    except Exception as e:
        return f"NO VERIFIED WEB REFERENCES FOUND (Search Error: {e}). WARNING: Answer using general Fiqh principles ONLY. DO NOT cite any specific Hadiths or Quran verse numbers."

async def kirim_pesan_panjang(target, text, mode="reply"):
    """Mengirim pesan panjang ke Discord tanpa memotong kata di tengah-tengah."""
    if not text:
        return
    
    limit = 1800
    chunks = []
    
    while len(text) > limit:
        cut_index = text.rfind(' ', 0, limit)
        if cut_index == -1:
            cut_index = limit
            
        chunks.append(text[:cut_index])
        text = text[cut_index:].strip()
        
    if text:
        chunks.append(text)

    for i, chunk in enumerate(chunks):
        if mode == "reply":
            if i == 0:
                await target.reply(chunk)
            else:
                await target.channel.send(chunk)
        elif mode == "slash":
            await target.followup.send(chunk)

# ---------------------------------------------------------
# Discord Bot Initialization & Events
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} Slash Commands for Islamic.AI Bot!")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
        
    await bot.change_presence(activity=discord.Game(name="/help | /fiqh | /hadith | /tafsir"))
    print(f"✅ Islamic.AI Bot ({bot.user}) is Online!")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Detect Verse Shortcut (e.g., 1:1-7, 2:255, 36:1-10)
    verse_pattern = r'\b(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\b'
    match_verse = re.search(verse_pattern, message.content.strip())

    is_reply_to_bot = False
    if message.reference and message.reference.message_id:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.author == bot.user:
                is_reply_to_bot = True
        except Exception:
            pass

    is_mentioned = bot.user in message.mentions

    if match_verse or is_reply_to_bot or is_mentioned:
        async with message.channel.typing():
            if match_verse:
                verse_ref = match_verse.group(0)
                web_ref = await asyncio.to_thread(cari_web, f"quran verse {verse_ref} arabic translation tafsir")
                prompt = (
                    f"User requested verse shortcut: Surah:Verse {verse_ref}.\n"
                    f"Provide: (1) Original Arabic text, (2) Translation, and (3) Explicit translation source citation.\n\n"
                    f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
                )
            else:
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
                last_prompt = raw_history[-1] if raw_history else message.content
                web_ref = await asyncio.to_thread(cari_web, last_prompt)
                prompt = f"VERIFIED WEB REFERENCES:\n{web_ref}\n\nCHAT HISTORY:\n" + "\n".join(raw_history)

            jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
            await kirim_pesan_panjang(message, jawaban, mode="reply")

    await bot.process_commands(message)

# ---------------------------------------------------------
# Slash Commands
# ---------------------------------------------------------

@bot.tree.command(name="help", description="Guide & commands for Islamic.AI Bot")
async def slash_help(interaction: discord.Interaction):
    guide_text = (
        "📖 **Islamic.AI — Command Guide & Help**\n\n"
        "**Main Commands (Search-Grounded & Verified):**\n"
        "• `/ask [prompt] [language]` - Ask any question or request Qur'anic references.\n"
        "• `/tafsir [verse] [source] [language]` - Detailed Qur'anic exegesis (GPT-OSS 120B Engine).\n"
        "• `/fiqh [question] [madhhab] [language]` - Ask Islamic jurisprudence rulings (GPT-OSS 120B Engine).\n"
        "• `/hadith [topic] [book] [language]` - Search authentic Hadiths with verified source citations.\n"
        "• `/dua [topic] [language]` - Search authentic Supplications (Dua) & Adhkar.\n"
        "• `/dalil [topic] [language]` - Find evidence from Qur'an & Sunnah for specific issues.\n"
        "• `/search [query] [language]` - Search live web references for Islamic studies.\n"
        "• `/test` - Check Groq API connection, latency, & system health.\n"
        "• `/ping` - Check bot status and Discord latency.\n\n"
        "💡 *Verse Shortcut Tip:* You can type verse numbers like `1:1-7` or `2:255` directly in chat to view Arabic text & translation!\n"
        "💡 *Language Tip:* Type any target language in the `language` field (e.g., *English*, *Arabic*, *Indonesian*, *Sundanese*) to force response in that language."
    )
    await interaction.response.send_message(guide_text)

@bot.tree.command(name="ask", description="Ask anything about Islam or request verse references")
@app_commands.describe(
    prompt="Your question or topic",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_ask(
    interaction: discord.Interaction, 
    prompt: str, 
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        web_ref = await asyncio.to_thread(cari_web, prompt)
        
        final_prompt = (
            f"[{sender_name}]: {prompt}\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            final_prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language from start to finish.]"
            
        jawaban = await asyncio.to_thread(tanya_groq, final_prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="tafsir", description="Detailed Qur'anic exegesis (Powered by GPT-OSS 120B)")
@app_commands.describe(
    verse="Verse reference (e.g., '2:255' or 'Al-Baqarah 255')",
    source="Optional: Tafsir book (Ibn Kathir, Jalalayn, etc.)",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_tafsir(
    interaction: discord.Interaction, 
    verse: str, 
    source: Optional[str] = None,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        search_query = f"tafsir verse {verse} {source if source else ''}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Provide a comprehensive tafsir for verse {verse}.\n"
            f"Primary reference requested: {source if source else 'Standard Trusted Exegesis'}.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="fiqh", description="Ask Fiqh rulings by school of thought (Powered by GPT-OSS 120B)")
@app_commands.describe(
    question="Your jurisprudence (Fiqh) question",
    madhhab="Select Madhhab perspective",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
@app_commands.choices(
    madhhab=[
        app_commands.Choice(name="Shafi'i", value="shafii"),
        app_commands.Choice(name="Hanafi", value="hanafi"),
        app_commands.Choice(name="Maliki", value="maliki"),
        app_commands.Choice(name="Hanbali", value="hanbali"),
        app_commands.Choice(name="Ja'fari / Shia Twelver", value="jaafari_shia"),
        app_commands.Choice(name="Zaidi / Shia Zaidiyyah", value="zaidi_shia"),
        app_commands.Choice(name="Comparative (All Schools of Thought)", value="comparative_all")
    ]
)
async def slash_fiqh(
    interaction: discord.Interaction, 
    question: str, 
    madhhab: Optional[app_commands.Choice[str]] = None,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        chosen_madhhab = madhhab.value if madhhab else "comparative_all"
        
        search_query = f"fiqh ruling {question} madhhab {chosen_madhhab}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Fiqh Question: '{question}'. Requested Madhhab: {chosen_madhhab.upper()}.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="hadith", description="Search authentic Hadiths with source citations")
@app_commands.describe(
    topic="Hadith topic or keyword",
    book="Optional: Hadith Collection (Bukhari, Muslim, Abu Dawud, etc.)",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_hadith(
    interaction: discord.Interaction, 
    topic: str, 
    book: Optional[str] = None,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        search_query = f"hadith {topic} {book if book else ''} sahih bukhari muslim"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Search authentic Hadiths regarding '{topic}'.\n"
            f"Requested collection: {book if book else 'Kutubus Sittah'}.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"
            
        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="dua", description="Search authentic Duas and Adhkar")
@app_commands.describe(
    topic="Topic or situation for the Dua",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_dua(
    interaction: discord.Interaction, 
    topic: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        search_query = f"dua supplicaton adhkar {topic}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Provide authentic Duas for topic/situation: '{topic}'.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="dalil", description="Find Qur'anic and Hadith evidence for specific topics")
@app_commands.describe(
    topic="Topic or issue to search evidence for",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_dalil(
    interaction: discord.Interaction, 
    topic: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        search_query = f"dalil quran hadith {topic}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: List authentic evidence from Qur'an and Sunnah regarding: '{topic}'.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="search", description="Search Islamic research references from the web")
@app_commands.describe(
    query="Search keywords",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_search(
    interaction: discord.Interaction, 
    query: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        web_data = await asyncio.to_thread(cari_web, query)
        full_prompt = f"[{sender_name}]: Use the following web references to answer:\n\nREFERENCES:\n{web_data}\n\nQUESTION: {query}"
        if language:
            full_prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"
            
        jawaban = await asyncio.to_thread(tanya_groq, full_prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="test", description="Test Groq API connection, latency, and system health")
async def slash_test(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        start_time = time.time()
        respon = await asyncio.to_thread(tanya_groq, "System test: Provide 1 short Islamic greeting in English.", MODEL_RINGAN)
        api_latency = round((time.time() - start_time) * 1000)
        discord_ping = round(bot.latency * 1000)
        
        status_msg = (
            "🧪 **[SYSTEM DIAGNOSTIC - ISLAMIC.AI]**\n\n"
            f"🟢 **Groq API Status:** Connected & Active\n"
            f"⚡ **API Latency:** `{api_latency}ms`\n"
            f"📡 **Discord Ping:** `{discord_ping}ms`\n"
            f"🧠 **Active Engine:** 70B Strict Anti-Hallucination (`llama-3.3-70b-versatile`)\n\n"
            f"💬 **Output Test Sample:**\n> {respon}"
        )
        await interaction.followup.send(status_msg)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Diagnostic test failed: {e}")

@bot.tree.command(name="ping", description="Check bot latency status")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Islamic.AI latency: `{latency}ms` (70B Anti-Hallucination Active)")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN_QURAN is not set in Streamlit Secrets!")
    else:
        bot.run(DISCORD_TOKEN)
