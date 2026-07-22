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
MODEL_BERAT = "openai/gpt-oss-120b"          # Primary Heavy Model (Tafsir & Fiqh)
MODEL_RINGAN = "llama-3.3-70b-versatile"     # High-Intelligence Model (Anti-Hallucination)
MODEL_CADANGAN = "llama-3.1-8b-instant"      # Emergency Fallback

SYSTEM_PROMPT = """
You are 'Islamic.AI', an authentic, highly respectful, and strictly factual AI assistant specialized in Islamic jurisprudence (Fiqh), Qur'an tafsir, authentic Hadiths, and Duas.

STRICT ANTI-HALLUCINATION & MANDATORY CITATION RULES:
1. MANDATORY SCHOLARLY / BOOK SOURCES IN EVERY ANSWER:
   - EVERY SINGLE RESPONSE MUST EXPLICITLY CITE ITS SOURCES (e.g., "Dikutip dari Tafsir Ibn Kathir", "Berdasarkan Kitab Al-Majmu' Imam an-Nawawi", "Menurut Fiqh al-Sunnah", or specific Hadith collections like Sahih Bukhari/Muslim).
   - If giving a general Fiqh explanation, explicitly state the classical book or recognized scholar/school of thought (Madhhab) it derives from.

2. HADITH & DALIL MANDATORY FORMAT:
   - When answering /hadith or /dalil: Always provide (1) Original Arabic Text (Matan), (2) Translation, and (3) Exact Collection Reference.
   - ONLY cite specific Hadiths or verse numbers if their exact reference exists in the provided 'VERIFIED SEARCH REFERENCES'.

3. ZERO HADITH FABRICATION FOR MODERN TOPICS:
   - For modern/contemporary topics (e.g., Gacha Games, Anime, Crypto, Video Games, NFTs):
     * DO NOT invent, quote, or cite ANY Hadith narrators or fake Surah numbers.
     * Explain modern topics ONLY using rational Islamic Fiqh principles (Gharar, Maysir, Israf) and cite general Fiqh maxims/consensus (e.g., "Berdasarkan Kaidah Fiqhiyyah dalam Fiqh Muamalah...").

4. STRICT TARGET LANGUAGE FORCING:
   - Always output your ENTIRE response strictly in the requested target language (e.g., Sundanese/Basa Sunda, English, Arabic, Indonesian).
   - Start directly with the answer without conversational chatter.

5. MANDATORY DISCLAIMER:
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
            "temperature": 0.0,  # 0.0 Murni Faktual
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
            res = ddgs.text(f"islam quran hadith fiqh tafsir {query_bersih}", max_results=4)
            for r in res:
                results.append(f"Title: {r['title']}\nContent: {r['body']}")
        
        if results:
            return "\n\n".join(results)
        else:
            return "NO VERIFIED WEB REFERENCES FOUND. WARNING: Answer using general Fiqh principles ONLY and cite general scholarly books/consensus. DO NOT cite specific fake Hadith numbers."
    except Exception as e:
        return f"NO VERIFIED WEB REFERENCES FOUND (Search Error: {e}). WARNING: Answer using general Fiqh principles ONLY and cite general scholarly books/consensus."

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
                web_ref = await asyncio.to_thread(cari_web, f"quran verse {verse_ref} arabic translation tafsir ibn kathir jalalayn")
                prompt = (
                    f"User requested verse shortcut: Surah:Verse {verse_ref}.\n"
                    f"Provide: (1) Original Arabic text, (2) Translation, and (3) Explicit Tafsir book / Translation source citation.\n\n"
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
                prompt = (
                    f"VERIFIED WEB REFERENCES:\n{web_ref}\n\n"
                    f"CHAT HISTORY:\n" + "\n".join(raw_history) + "\n\n"
                    f"[INSTRUCTION: Remember to explicitly cite the book, kitāb, or tafsir source for your explanation.]"
                )

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
        "**Main Commands (Search-Grounded & Cited):**\n"
        "• `/ask [prompt] [language]` - Ask any question (Includes explicit kitāb/scholarly sources).\n"
        "• `/tafsir [verse] [source] [language]` - Detailed Qur'anic exegesis with Tafsir citations.\n"
        "• `/fiqh [question] [madhhab] [language]` - Ask Islamic jurisprudence rulings with Fiqh book sources.\n"
        "• `/hadith [topic] [book] [language]` - Search authentic Hadiths with Arabic text & collection citations.\n"
        "• `/dua [topic] [language]` - Search authentic Supplications (Dua) & Adhkar sources.\n"
        "• `/dalil [topic] [language]` - Find evidence from Qur'an & Sunnah (Arabic + Translation + Citations).\n"
        "• `/search [query] [language]` - Search live web references for Islamic studies.\n"
        "• `/test` - Check Groq AI connection, latency, & system health.\n"
        "• `/ping` - Check bot status and Discord latency.\n\n"
        "💡 *Verse Shortcut Tip:* Type verse numbers like `1:1-7` or `2:255` directly in chat to view Arabic text & translation!\n"
        "💡 *Language Tip:* Type any target language in the `language` field (e.g., *English*, *Arabic*, *Indonesian*, *Sundanese*) to force response in that language."
    )
    await interaction.response.send_message(guide_text)

@bot.tree.command(name="ask", description="Ask anything about Islam (Explicit book citations included)")
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
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}\n\n"
            f"[INSTRUCTION: Always explicitly cite the classical Fiqh/Tafsir book or scholar source for this answer.]"
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
        search_query = f"tafsir verse {verse} {source if source else 'ibn kathir jalalayn'}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Provide a comprehensive tafsir for verse {verse}.\n"
            f"Primary reference requested: {source if source else 'Tafsir Ibn Kathir / Jalalayn'}.\n"
            f"MANDATORY REQUIREMENT: State the exact name of the Tafsir book used.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="fiqh", description="Ask Fiqh rulings with kitāb sources (Powered by GPT-OSS 120B)")
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
        
        search_query = f"fiqh ruling kitab {question} madhhab {chosen_madhhab}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Fiqh Question: '{question}'. Requested Madhhab: {chosen_madhhab.upper()}.\n"
            f"MANDATORY REQUIREMENT: Cite the specific Fiqh book or classical scholar source for this ruling.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="hadith", description="Search authentic Hadiths with original Arabic text & citations")
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
        search_query = f"matan hadits arab {topic} {book if book else 'sahih bukhari muslim'}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Search authentic Hadiths regarding '{topic}'. Requested Collection: {book if book else 'Kutubus Sittah'}.\n"
            f"MANDATORY FORMAT:\n"
            f"1. Original Arabic Matan Text\n"
            f"2. Complete Translation\n"
            f"3. Exact Collection & Book Citation (e.g., HR. Bukhari No. xxx / Sahih Muslim)\n\n"
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
        search_query = f"doa dzikir arab latin terjemahan {topic}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Provide authentic Duas for topic/situation: '{topic}'.\n"
            f"Provide: Original Arabic text, transliteration, translation, and kitāb/hadith reference source.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="dalil", description="Find Qur'anic and Hadith evidence (Arabic + Translation + Sources)")
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
        search_query = f"matan hadits sahih bukhari muslim ayat quran dalil {topic}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Provide authentic Dalil (Qur'an verses and Sahih Hadiths) for topic: '{topic}'.\n"
            f"MANDATORY FORMAT:\n"
            f"1. Original Arabic Text\n"
            f"2. Translation\n"
            f"3. Explicit Reference Source & Kitāb Name (Surah name/number or Hadith Collection)\n\n"
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
        full_prompt = f"[{sender_name}]: Use the following web references to answer and cite the source books:\n\nREFERENCES:\n{web_data}\n\nQUESTION: {query}"
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
            f"🧠 **Active Engine:** 70B Cited RAG (`llama-3.3-70b-versatile`)\n\n"
            f"💬 **Output Test Sample:**\n> {respon}"
        )
        await interaction.followup.send(status_msg)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Diagnostic test failed: {e}")

@bot.tree.command(name="ping", description="Check bot latency status")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Islamic.AI latency: `{latency}ms` (Source Citation Active)")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN_QURAN is not set in Streamlit Secrets!")
    else:
        bot.run(DISCORD_TOKEN)
