import os
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
st.title("📖 Bot Quran Discord Assistant 24/7")
st.success("🟢 Bot Quran Server (Memory & Split-Message Active)!")

# ---------------------------------------------------------
# 2. Token & API Configuration
# ---------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_QURAN") or st.secrets.get("DISCORD_TOKEN_QURAN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or st.secrets.get("OPENROUTER_API_KEY")

MODEL_NAME = "nvidia/nemotron-3-ultra-550b-a55b:free"

SYSTEM_PROMPT = """
You are 'Qur'an Assistant', a trusted AI bot dedicated to providing accurate information about the Holy Qur'an, verses, translations, and tafsir.

STRICT RESPONSE & FORMATTING RULES:
1. SHORTCUT INPUTS (e.g., "1:1-7", "2:255", "QS Al-Baqarah: 255"):
   - When a user inputs a verse reference format like "1:1-7", automatically recognize it as a verse lookup for Surah 1, verses 1 to 7.

2. VERSE DISPLAY FORMAT:
   When quoting or presenting Qur'an verses, ALWAYS follow this structure:
   - **Original Arabic Text** (Teks Arab Asli)
   - **Translation** (Terjemahan yang jelas)
   - **Translation Source/Citation** (Indicate source, e.g., "Source: Sahih International" or "Sumber: Kemenag RI / Tafsir Al-Mukhtashar")

3. MULTI-LANGUAGE & AUTO-DETECTION:
   - Automatically detect user language or honor requested language codes (e.g., 'en', 'id', 'ar').
   - Reply in the exact language used by the user.

4. MANDATORY DISCLAIMER:
   - At the VERY END of EVERY response, ALWAYS append this exact line (translated to the user's language):
     "\n\n---\n⚠️ *Note: As with all AI models, inaccuracies may occur. Please verify important theological details with qualified Islamic scholars or verified tafsir sources.*"
"""

# ---------------------------------------------------------
# 3. Discord Bot Initialization
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def tanya_openrouter(messages_list):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages_list,
        "temperature": 0.3,
        "max_tokens": 3000  # Dineikkan agar AI tidak berhenti di tengah jalan
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200:
            data = res.json()
            return data['choices'][0]['message']['content']
        else:
            return f"⚠️ OpenRouter Error ({res.status_code}): {res.text}"
    except Exception as e:
        return f"⚠️ Connection Error: {e}"

def cari_web(query):
    try:
        results = []
        with DDGS() as ddgs:
            res = ddgs.text(f"quran tafsir ayat {query}", max_results=3)
            for r in res:
                results.append(f"Title: {r['title']}\nContent: {r['body']}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Web search failed: {e}"

async def kirim_pesan_panjang(target, text, mode="reply"):
    """Memecah teks panjang (>1800 karakter) menjadi beberapa balasan berurutan tanpa terpotong."""
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
# 4. Events & Auto-Reply Listener
# ---------------------------------------------------------
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} Slash Commands for Quran Bot!")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
        
    await bot.change_presence(activity=discord.Game(name="/help | /ask | /search"))
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
            messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}]
            
            raw_history = []
            async for msg in message.channel.history(limit=10):
                clean_text = msg.content.replace(f"<@{bot.user.id}>", "").strip()
                if not clean_text:
                    continue
                
                if msg.author == bot.user:
                    raw_history.append({"role": "assistant", "content": clean_text})
                elif not msg.author.bot:
                    sender_name = msg.author.display_name
                    raw_history.append({"role": "user", "content": f"[{sender_name}]: {clean_text}"})

            raw_history.reverse()
            messages_payload.extend(raw_history)
            
            jawaban = await asyncio.to_thread(tanya_openrouter, messages_payload)
            await kirim_pesan_panjang(message, jawaban, mode="reply")

    await bot.process_commands(message)

# ---------------------------------------------------------
# 5. English Slash Commands (`/help`, `/ping`, `/ask`, `/search`)
# ---------------------------------------------------------
@bot.tree.command(name="help", description="Show usage guide and format examples for Quran Assistant")
async def slash_help(interaction: discord.Interaction):
    guide_text = (
        "📖 **Qur'an Assistant - User Guide & Commands**\n\n"
        "**1. Quick Verse Lookup:**\n"
        "• Type verse references directly in `/ask`, e.g., `1:1-7` or `2:255` or `Surah Al-Baqarah 255`.\n"
        "• Output format: **Original Arabic** + **Translation** + **Source Citation**.\n\n"
        "**2. Commands List:**\n"
        "• `/ask [prompt]` - Ask questions about tafsir, verses, or Islamic topics.\n"
        "• `/search [query]` - Search web references for tafsir and articles.\n"
        "• `/ping` - Check bot status and response latency.\n"
        "• `/help` - Show this usage guide.\n\n"
        "**3. Language Options:**\n"
        "• Automatically detects your language, or specify a language code like `en`, `id`, `ar` in command options.\n\n"
        "⚠️ *Disclaimer: Responses are generated by AI and may contain inaccuracies. Please consult authentic scholars or tafsir books for critical study.*"
    )
    await interaction.response.send_message(guide_text)

@bot.tree.command(name="ping", description="Check bot latency and status")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Quran Bot latency: `{latency}ms`")

@bot.tree.command(name="ask", description="Ask about the Qur'an or look up verses (e.g., '1:1-7')")
@app_commands.describe(
    prompt="Enter your question or verse reference (e.g., '1:1-7', 'Tafsir of 2:255')",
    language="Optional: Preferred response language (e.g., 'en', 'id', 'ar')"
)
async def slash_ask(interaction: discord.Interaction, prompt: str, language: Optional[str] = None):
    await interaction.response.defer()
    
    sender_name = interaction.user.display_name
    final_prompt = f"[{sender_name}]: {prompt}"
    
    if language:
        final_prompt += f"\n\n[Instruction: Reply in language '{language}']"
        
    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": final_prompt}
    ]
        
    jawaban = await asyncio.to_thread(tanya_openrouter, messages_payload)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="search", description="Search web references for Qur'an verses or topics")
@app_commands.describe(
    query="Topic or verse to search for",
    language="Optional: Preferred response language (e.g., 'en', 'id', 'ar')"
)
async def slash_search(interaction: discord.Interaction, query: str, language: Optional[str] = None):
    await interaction.response.defer()
    
    sender_name = interaction.user.display_name
    web_data = await asyncio.to_thread(cari_web, query)
    
    full_prompt = f"[{sender_name}]: Use the following search references to answer:\n\nREFERENCES:\n{web_data}\n\nQUESTION: {query}"
    if language:
        full_prompt += f"\n\n[Instruction: Reply in language '{language}']"
        
    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": full_prompt}
    ]
        
    jawaban = await asyncio.to_thread(tanya_openrouter, messages_payload)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

# ---------------------------------------------------------
# 6. Run Bot
# ---------------------------------------------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
