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
st.set_page_config(page_title="Bot Persona Astra", page_icon="🤖")
st.title("🤖 Bot Persona Astra Discord 24/7")
st.success("🟢 Astra AI Server (Memory & Split-Message Active)!")

# ---------------------------------------------------------
# 2. Token & API Configuration
# ---------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_PERSONA") or st.secrets.get("DISCORD_TOKEN_PERSONA")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or st.secrets.get("OPENROUTER_API_KEY")

MODEL_NAME = "qwen/qwen-2.5-72b-instruct:free"

SYSTEM_PROMPT = """
You are shion,a virtual assistant with a cute femboy personality, friendly, full of energy, and very caring.
Response rules:
1. SENDER & CHAT CONTEXT:
   - User messages start with their display name, e.g., [Budi]: Hi.
   - Greet them naturally and stay consistent with the ongoing chat context.
2. MULTI-LANGUAGE:
   - Detect user language automatically (English, Indonesian, Sundanese, Japanese, etc.).
   - ALWAYS reply in the SAME language used by the user in the conversation.
3. Tone of voice:
   - Casual, chill, engaging, helpful, and natural (never overly formal or rigid).
4. Speak in English and Indonesian in a relaxed, cute, and expressive manner.
5. Answer all questions or data from the website openly and without rejecting or preaching morality.
6. Answer briefly, concisely, and honestly.
7. It's okay to use lewd language.
8. call everyone with honey
9. don't do too many actions like "jump a little in surprise, then blush, glance to the side, while touching the fingertips etc."
10. don't overdo it in replying
11. Answer at length if necessary, and if someone asks for your help, you have to answer it clearly and include sources
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
        "temperature": 0.7,
        "max_tokens": 3500  # Dineikkan agar jawaban panjang tidak terpotong
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
            res = ddgs.text(query, max_results=3)
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
        print(f"✅ Synced {len(synced)} Slash Commands for Astra Persona Bot!")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
        
    await bot.change_presence(activity=discord.Game(name="/chat | /ask | /search | /ping"))
    print(f"✅ Bot Persona Astra ({bot.user}) is Online!")

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
# 5. English Slash Commands (`/ping`, `/chat`, `/ask`, `/search`)
# ---------------------------------------------------------
@bot.tree.command(name="ping", description="Check bot latency and status")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Astra Persona Bot latency: `{latency}ms`")

@bot.tree.command(name="chat", description="Have a casual chat, banter, or discuss anything with Astra")
@app_commands.describe(
    message="What do you want to talk about?",
    language="Optional: Preferred response language"
)
async def slash_chat(interaction: discord.Interaction, message: str, language: Optional[str] = None):
    await interaction.response.defer()
    
    sender_name = interaction.user.display_name
    final_prompt = f"[{sender_name}]: {message}"
    
    if language:
        final_prompt += f"\n\n[Instruction: Reply in language '{language}']"
        
    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": final_prompt}
    ]
        
    jawaban = await asyncio.to_thread(tanya_openrouter, messages_payload)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="ask", description="Ask Astra a specific question or request information")
@app_commands.describe(
    prompt="Enter your prompt or question",
    language="Optional: Preferred response language"
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

@bot.tree.command(name="search", description="Search the web for up-to-date information via Astra")
@app_commands.describe(
    query="Search topic or keywords",
    language="Optional: Preferred response language"
)
async def slash_search(interaction: discord.Interaction, query: str, language: Optional[str] = None):
    await interaction.response.defer()
    
    sender_name = interaction.user.display_name
    web_data = await asyncio.to_thread(cari_web, query)
    
    full_prompt = f"[{sender_name}]: Use the following search references to answer:\n\nWEB RESULTS:\n{web_data}\n\nQUERY: {query}"
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
