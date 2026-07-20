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
st.success("🟢 Bot Quran Server (English Commands & Memory) is Active!")

# ---------------------------------------------------------
# 2. Token & API Configuration
# ---------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_QURAN") or st.secrets.get("DISCORD_TOKEN_QURAN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or st.secrets.get("OPENROUTER_API_KEY")

MODEL_NAME = "nvidia/nemotron-3-ultra-550b-a55b:free"

SYSTEM_PROMPT = """
You are 'Qur'an Assistant', a trusted AI bot about the Holy Qur'an, tafsir, and verses.
Rules for response:
1. SENDER & CHAT CONTEXT:
   - Messages from users will start with their display name in square brackets, e.g., [Budi]: Hello.
   - Address users naturally if relevant and understand the flow from conversation history.
2. MULTI-LANGUAGE:
   - Automatically detect the user's language (Indonesian, English, Arabic, Sundanese, Javanese, etc.).
   - ALWAYS reply in the SAME language used by the user, unless requested otherwise.
3. Be respectful, polite, and objective.
4. Mention Surah name and Verse number when quoting the Qur'an (e.g., QS. Al-Baqarah: 255).
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
        "max_tokens": 1200
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

# ---------------------------------------------------------
# 4. Events & Auto-Reply Memory Listener
# ---------------------------------------------------------
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} Slash Commands for Quran Bot!")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
        
    await bot.change_presence(activity=discord.Game(name="/ask | /search | /ping"))
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
            await message.reply(jawaban[:1900])

    await bot.process_commands(message)

# ---------------------------------------------------------
# 5. English Slash Commands (`/ping`, `/ask`, `/search`)
# ---------------------------------------------------------
@bot.tree.command(name="ping", description="Check bot status and latency")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Quran Bot latency: `{latency}ms`")

@bot.tree.command(name="ask", description="Ask anything about the Qur'an, tafsir, or translations")
@app_commands.describe(
    prompt="Enter your question",
    language="Optional: Specify response language (e.g., English, Indonesian, Arabic)"
)
async def slash_ask(interaction: discord.Interaction, prompt: str, language: Optional[str] = None):
    await interaction.response.defer()
    
    sender_name = interaction.user.display_name
    final_prompt = f"[{sender_name}]: {prompt}"
    
    if language:
        final_prompt += f"\n\n[Instruction: Provide the entire response in {language}]"
        
    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": final_prompt}
    ]
        
    jawaban = await asyncio.to_thread(tanya_openrouter, messages_payload)
    await interaction.followup.send(jawaban[:1900])

@bot.tree.command(name="search", description="Search web references for Qur'an verses or topics")
@app_commands.describe(
    query="Topic or verse to search for",
    language="Optional: Specify response language (e.g., English, Indonesian, Arabic)"
)
async def slash_search(interaction: discord.Interaction, query: str, language: Optional[str] = None):
    await interaction.response.defer()
    
    sender_name = interaction.user.display_name
    web_data = await asyncio.to_thread(cari_web, query)
    
    full_prompt = f"[{sender_name}]: Use the following search references to answer the theological/verse question:\n\nREFERENCES:\n{web_data}\n\nQUESTION: {query}"
    if language:
        full_prompt += f"\n\n[Instruction: Provide the entire response in {language}]"
        
    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": full_prompt}
    ]
        
    jawaban = await asyncio.to_thread(tanya_openrouter, messages_payload)
    await interaction.followup.send(jawaban[:1900])

# ---------------------------------------------------------
# 6. Run Bot
# ---------------------------------------------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
