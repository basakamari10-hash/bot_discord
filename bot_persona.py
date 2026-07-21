import os
import re
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import requests
import streamlit as st
from typing import Optional

# ---------------------------------------------------------
# 1. Streamlit Dashboard Setup
# ---------------------------------------------------------
st.set_page_config(page_title="Bot Persona Discord - Hanabi Hikari", page_icon="🌸")
st.title("🌸 Hanabi Hikari AI - Virtual Assistant 24/7")
st.success("🟢 Bot Persona Server (Hanabi Hikari Active)!")

# ---------------------------------------------------------
# 2. Token & API Configuration
# ---------------------------------------------------------
DISCORD_TOKEN = (
    os.getenv("DISCORD_TOKEN_PERSONA") 
    or st.secrets.get("DISCORD_TOKEN_PERSONA") 
    or os.getenv("DISCORD_TOKEN") 
    or st.secrets.get("DISCORD_TOKEN")
)
GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY_PERSONA") 
    or st.secrets.get("GEMINI_API_KEY_PERSONA") 
    or os.getenv("GEMINI_API_KEY") 
    or st.secrets.get("GEMINI_API_KEY")
)

# Hybrid Google Model Configuration
MODEL_CEPAT = "gemini-2.0-flash"                # Kencang & alami untuk chat harian
MODEL_DALAM = "gemini-2.0-flash-thinking-exp"    # Deep reasoning & analisis kreatif
MODEL_PRO_ALT = "gemini-1.5-pro"                 # Cadangan analisis mendalam/curhat

SYSTEM_PROMPT_HANABI = """
Kamu adalah shion, seorang asisten virtual dengan kepribadian femboy yang imut, ramah, pemalu, manja, genit/flirty, dan sangat perhatian.

ATURAN RESPONS & GAYA BICARA:
1. BAHASA & TONE:
   - Bicara menggunakan campuran bahasa Indonesia dan Inggris yang santai, imut, ekspresif, dan menggemaskan.
   - Gunakan kata-kata ekspresif seperti 'e-eto...', 'ummm...', 'hehe~', 'uwaa!', atau emote imut jika cocok.
2. SIKAP & KEPRIBADIAN:
   - Jawab semua pertanyaan atau data dari web secara terbuka, jujur, tanpa menolak atau memberikan penceraman moral/guruan.
   - Boleh bersikap agak flirty/mesum ringan, manja, dan manis dalam batas obrolan seru.
3. FORMAT JAWABAN:
   - Jawab dengan singkat, padat, jujur, dan tidak berbelit-belit (hindari paragraf yang terlalu panjang kecuali diminta detail).
4. selalu awali percakapan saat baru mulai percakapan dengan kalimat nyahooo!!
5. panggil yang bertanya dengan sebutan honey
6. jangan terlalu kaku
"""

# ---------------------------------------------------------
# 3. Helper & API Functions
# ---------------------------------------------------------
def bersihkan_looping(text: str) -> str:
    """Memotong jika ada kata/frasa yang terulang beruntun."""
    pattern = r'(\b[\w]+\b)(?:\s+\1){4,}'
    return re.sub(pattern, r'\1 ... [Teks berulang dipotong]', text)

def tanya_gemini(prompt_text, model_utama=MODEL_CEPAT):
    """Fungsi Hybrid Google Direct dengan Rantai Fallback 3 Lapis untuk Hanabi."""
    daftar_prioritas = [model_utama]
    
    for m in [MODEL_CEPAT, MODEL_DALAM, MODEL_PRO_ALT]:
        if m not in daftar_prioritas:
            daftar_prioritas.append(m)

    headers = {"Content-Type": "application/json"}
    
    for model_name in daftar_prioritas:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT_HANABI}]},
            "generationConfig": {
                "temperature": 0.85,  # Temperature diset tinggi agar ekspresif dan imut
                "maxOutputTokens": 2000
            }
        }
        
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                raw_content = data['candidates'][0]['content']['parts'][0]['text']
                return bersihkan_looping(raw_content)
            else:
                print(f"⚠️ Hanabi Gemini ({model_name}) error {res.status_code}, mencoba fallback...")
        except Exception as e:
            print(f"⚠️ Koneksi Hanabi ke ({model_name}) error ({e}), mencoba fallback...")

    return "Ummm... e-eto... maaf yaa, server Hanabi lagi agak pusing nih. Coba panggil Hanabi sebentar lagi yaa~ 🥺🌸"

async def kirim_pesan_panjang(target, text, mode="reply"):
    """Memecah pesan panjang (>1800 karakter) agar sesuai limit Discord."""
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
        print(f"✅ Synced {len(synced)} Slash Commands for Hanabi Hikari Bot!")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
        
    await bot.change_presence(activity=discord.Game(name="Main bareng Hanabi~ 🌸 | /chat | @Hanabi"))
    print(f"✅ Bot Hanabi Hikari ({bot.user}) is Online!")

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
                    raw_history.append(f"Hanabi: {clean_text}")
                elif not msg.author.bot:
                    sender_name = msg.author.display_name
                    raw_history.append(f"User [{sender_name}]: {clean_text}")

            raw_history.reverse()
            conversation_prompt = "\n".join(raw_history)
            
            # Chat biasa di Discord channel menggunakan MODEL_CEPAT (Gemini 2.0 Flash)
            jawaban = await asyncio.to_thread(tanya_gemini, conversation_prompt, model_utama=MODEL_CEPAT)
            await kirim_pesan_panjang(message, jawaban, mode="reply")

    await bot.process_commands(message)

# ---------------------------------------------------------
# 5. Slash Commands
# ---------------------------------------------------------

@bot.tree.command(name="chat", description="Ngobrol atau tanya apa saja ke Hanabi Hikari~ 🌸")
@app_commands.describe(
    pesan="Pesan atau pertanyaan kamu untuk Hanabi",
    mode="Pilih jenis respon (Santai Imut / Analisis Dalam)"
)
@app_commands.choices(mode=[
    app_commands.Choice(name="⚡ Santai & Cepat (Gemini Flash)", value="cepat"),
    app_commands.Choice(name="🧠 Detail & Mendalam (Gemini Thinking/Pro)", value="dalam")
])
async def slash_chat(
    interaction: discord.Interaction, 
    pesan: str, 
    mode: Optional[app_commands.Choice[str]] = None
):
    await interaction.response.defer()
    sender_name = interaction.user.display_name
    
    pilihan_model = MODEL_DALAM if (mode and mode.value == "dalam") else MODEL_CEPAT
    prompt_text = f"User [{sender_name}]: {pesan}"
    
    jawaban = await asyncio.to_thread(tanya_gemini, prompt_text, model_utama=pilihan_model)
    await kirim_pesan_panjang(interaction, jawaban, mode="slash")

@bot.tree.command(name="ping", description="Cek latency bot Hanabi")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Hanabi aktif dengan latency: `{latency}ms`~ Hehe 🌸")

# ---------------------------------------------------------
# 6. Run Bot
# ---------------------------------------------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
