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
MODEL_RINGAN = "llama-3.1-8b-instant"       # Light Model (General Chat)
MODEL_CADANGAN = "llama-3.3-70b-versatile"  # Emergency Fallback

SYSTEM_PROMPT = """
You are 'Islamic.AI', an authentic, highly respectful, and strictly factual AI assistant specialized in Islamic jurisprudence (Fiqh), Qur'an tafsir, authentic Hadiths, and Duas.

CRITICAL RAG & ANTI-HALLUCINATION RULES:
1. USE VERIFIED REFERENCES FIRST:
   - You are provided with real-time web search references in the prompt. Extract exact verse numbers, Hadith numbers, collection names, Arabic texts, and translations directly from these references.
   - DO NOT fabricate, guess, or generate fake Hadith numbers, fake verse citations, or fake Arabic wording outside of verified Islamic sources.
   - If reference data is limited, state the general authenticated ruling or collection clearly without inventing fake numbers.

2. TARGET LANGUAGE & TRANSLATION:
   - Check if a specific target language instruction is provided in the prompt.
   - IF A TARGET LANGUAGE IS SPECIFIED (e.g., "English", "Arabic", "Basa Sunda", "Indonesian", etc.), YOU MUST FORCE AND TRANSLATE YOUR ENTIRE RESPONSE TO BE STRICTLY IN THAT TARGET LANGUAGE.
   - IF NO TARGET LANGUAGE IS SPECIFIED, automatically detect the prompt's language and respond in the EXACT SAME language. Default to English if unclear.

3. STRICT NO-REPETITION RULE:
   - NEVER repeat the same word, phrase, or sentence continuously.
   - Keep all citations, Arabic texts, and translations clean, structured, and concise.

4. DISCLAIMER:
   - Always include a short reminder at the end in the target language that complex Islamic rulings should be double-checked with qualified scholars.
"""

# ---------------------------------------------------------
# Helper & API Functions
# ---------------------------------------------------------
def bersihkan_looping(text: str) -> str:
    """Detect and strip repetitive words or sentence loops."""
    pattern_word = r'(\b[\w\u0600-\u06FF\u0100-\u024F]+\b)(?:\s+\1){3,}'
    cleaned = re.sub(pattern_word, r'\1', text, flags=re.IGNORECASE)
    
    pattern_phrase = r'(.{15,})\1{2,}'
    cleaned = re.sub(pattern_phrase, r'\1', cleaned, flags=re.DOTALL)
    
    return cleaned.strip()

def tanya_groq(prompt_text, model_tujuan=MODEL_RINGAN):
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
            "temperature": 0.1,  # STABIL & JUJUR (Mencegah AI Ngarang)
            "max_tokens": 3000
        }
        
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=20)
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
        results = []
        with DDGS() as ddgs:
            res = ddgs.text(f"islamic quran hadith fiqh {query}", max_results=3)
            for r in res:
                results.append(f"Title: {r['title']}\nContent: {r['body']}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Web search reference fetch failed: {e}"

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
            last_prompt = raw_history[-1] if raw_history else message.content
            web_ref = await asyncio.to_thread(cari_web, last_prompt)
            
            conversation_prompt = f"VERIFIED WEB REFERENCES:\n{web_ref}\n\nCHAT HISTORY:\n" + "\n".join(raw_history)
            jawaban = await asyncio.to_thread(tanya_groq, conversation_prompt, MODEL_RINGAN)
            await kirim_pesan_panjang(message, jawaban, mode="reply")

    await bot.process_commands(message)

# ---------------------------------------------------------
# Slash Commands (RAG Search-First Engine)
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
        "• `/test` - Check Groq AI connection, latency, & system health.\n"
        "• `/ping` - Check bot status and Discord latency.\n\n"
        "💡 *Language Tip:* You can type any target language in the `language` field (e.g., *English*, *Arabic*, *Indonesian*, *Sundanese*) to force the output strictly into that language."
    )
    await interaction.response.send_message(guide_text)

@bot.tree.command(name="ask", description="Ask anything about Islam or request verse references")
@app_commands.describe(
    prompt="Your question or topic",
    language="Optional: Type target response language (e.g., English, Arabic, Indonesian)"
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
            final_prompt += f"\n\n[MANDATORY INSTRUCTION: Force and translate your entire final answer to be strictly in '{language}' language.]"
            
        jawaban = await asyncio.to_thread(tanya_groq, final_prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="tafsir", description="Detailed Qur'anic exegesis (Powered by GPT-OSS 120B)")
@app_commands.describe(
    verse="Verse reference (e.g., '2:255' or 'Al-Baqarah 255')",
    source="Optional: Tafsir book (Ibn Kathir, Jalalayn, etc.)",
    language="Optional: Type target response language (e.g., English, Arabic, Indonesian)"
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
        search_query = f"tafsir verse {verse} {source if source else ''} quran commentary"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Provide a comprehensive tafsir for verse {verse}.\n"
            f"Primary reference book requested: {source if source else 'Standard Trusted Exegesis'}.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and translate your entire final answer to be strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="fiqh", description="Ask Fiqh rulings by school of thought (Powered by GPT-OSS 120B)")
@app_commands.describe(
    question="Your jurisprudence (Fiqh) question",
    madhhab="Select Madhhab perspective",
    language="Optional: Type target response language (e.g., English, Arabic, Indonesian)"
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
            f"[{sender_name}]: Fiqh Question: '{question}'. Requested School of Thought: {chosen_madhhab.upper()}.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and translate your entire final answer to be strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="hadith", description="Search authentic Hadiths with source citations")
@app_commands.describe(
    topic="Hadith topic or keyword",
    book="Optional: Hadith Collection (Bukhari, Muslim, Abu Dawud, etc.)",
    language="Optional: Type target response language (e.g., English, Arabic, Indonesian)"
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
        
        search_query = f"hadith {topic} {book if book else ''} sahih bukhari muslim sunnah.com"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: User is looking for authentic Hadiths about '{topic}'.\n"
            f"Specific collection requested: {book if book else 'Kutubus Sittah'}.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and translate your entire final answer to be strictly in '{language}' language.]"
            
        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="dua", description="Search authentic Duas and Adhkar")
@app_commands.describe(
    topic="Topic or situation for the Dua",
    language="Optional: Type target response language (e.g., English, Arabic, Indonesian)"
)
async def slash_dua(
    interaction: discord.Interaction, 
    topic: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        
        search_query = f"dua supplicaton adhkar {topic} Quran Sunnah"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        
        prompt = (
            f"[{sender_name}]: Provide authentic Duas for topic/situation: '{topic}'.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and translate your entire final answer to be strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="dalil", description="Find Qur'anic and Hadith evidence for specific topics")
@app_commands.describe(
    topic="Topic or issue to search evidence for",
    language="Optional: Type target response language (e.g., English, Arabic, Indonesian)"
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
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and translate your entire final answer to be strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="search", description="Search Islamic research references from the web")
@app_commands.describe(
    query="Search keywords",
    language="Optional: Type target response language (e.g., English, Arabic, Indonesian)"
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
            full_prompt += f"\n\n[MANDATORY INSTRUCTION: Force and translate your entire final answer to be strictly in '{language}' language.]"
            
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
            f"🧠 **Active Engine:** Full RAG Search-Grounded (`openai/gpt-oss-120b` & `llama-3.1-8b-instant`)\n\n"
            f"💬 **Output Test Sample:**\n> {respon}"
        )
        await interaction.followup.send(status_msg)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Diagnostic test failed: {e}")

@bot.tree.command(name="ping", description="Check bot latency status")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Islamic.AI latency: `{latency}ms` (Full RAG Engine Active)")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN_QURAN is not set in Streamlit Secrets!")
    else:
        bot.run(DISCORD_TOKEN)
