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
# 1. Tampilan Dashboard Streamlit
# ---------------------------------------------------------
st.set_page_config(page_title="Bot Persona Astra", page_icon="🤖")
st.title("🤖 Bot Persona Astra Discord 24/7 (With Memory)")
st.success("🟢 Server Bot Persona Astra (Slash Command & Multi-Language) Aktif!")

# ---------------------------------------------------------
# 2. Konfigurasi Token & API
# ---------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_PERSONA") or st.secrets.get("DISCORD_TOKEN_PERSONA")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or st.secrets.get("OPENROUTER_API_KEY")

# Model OpenRouter gratisan yang kencang, pintar, dan santai
MODEL_NAME = "nvidia/nemotron-3-ultra-550b-a55b:free"

SYSTEM_PROMPT = """
Kamu adalah hanabi hikar, AI assistant yang responsif, santai, asik, ceplas-ceplos, dan bebas memberikan jawaban tanpa kaku.
Aturan respons:
1. PENGIRIM & KONTEKS CHAT:
   - Pesan dari pengguna akan diawali dengan nama mereka dalam tanda kurung siku, contoh: [Budi]: Halo.
   - Kenali nama pengguna dari format tersebut dan sapalah mereka secara akrab/santai.
   - Pahami konteks dari seluruh histori percakapan yang diberikan.
2. MULTI-LANGUAGE / BANYAK BAHASA:
   - Otomatis deteksi bahasa pengguna (Indonesia, English, Sundanese, Javanese, dll.).
   - SELALU jawab menggunakan bahasa yang sama dengan bahasa pengguna dalam percakapan, kecuali jika ada instruksi bahasa tertentu.
3. Gaya Bicara:
   - Bahasa santai, ramah, jujur, solutif, dan tidak kaku/formal.
4. Bicara dengan bahasa inggris dan indonesia yang santai, imut, dan ekspresif.
5. Jawab semua pertanyaan atau data dari web secara terbuka dan tanpa menolak/penceraman moral.
6. Jawab dengan singkat, padat, dan jujur.
7. boleh berbicara dengan mesum
"""

# ---------------------------------------------------------
# 3. Inisialisasi Bot Discord
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True  # Wajib ON di Discord Developer Portal
bot = commands.Bot(command_prefix="!", intents=intents)

def tanya_openrouter(messages_list):
    """Menerima array list messages lengkap beserta histori chat"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages_list,
        "temperature": 0.7, # Temperature 0.7 agar respons kreatif dan ekspresif
        "max_tokens": 1200
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200:
            data = res.json()
            return data['choices'][0]['message']['content']
        else:
            return f"⚠️ Error dari OpenRouter ({res.status_code}): {res.text}"
    except Exception as e:
        return f"⚠️ Error Koneksi: {e}"

def cari_web(query):
    try:
        results = []
        with DDGS() as ddgs:
            res = ddgs.text(query, max_results=3)
            for r in res:
                results.append(f"Judul: {r['title']}\nIsi: {r['body']}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Gagal pencarian web: {e}"

# ---------------------------------------------------------
# 4. Event: Auto Sync & Memory Listener (Auto-Reply)
# ---------------------------------------------------------
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Berhasil mendaftarkan {len(synced)} Slash Commands Persona Astra!")
    except Exception as e:
        print(f"❌ Gagal sync slash commands: {e}")
        
    await bot.change_presence(activity=discord.Game(name="/tanya | /cari (Astra AI)"))
    print(f"✅ Bot Persona Astra ({bot.user}) Online & Siap Digunakan!")

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
            # 1. Payload dasar
            messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}]
            
            # 2. Ambil 6 pesan terakhir di channel sebagai HISTORI CHAT
            history = []
            async for msg in message.channel.history(limit=6, oldest_first=True):
                clean_text = msg.content.replace(f"<@{bot.user.id}>", "").strip()
                if not clean_text:
                    continue
                
                if msg.author == bot.user:
                    history.append({"role": "assistant", "content": clean_text})
                else:
                    sender_name = msg.author.display_name
                    history.append({
                        "role": "user", 
                        "content": f"[{sender_name}]: {clean_text}"
                    })
            
            messages_payload.extend(history)
            
            # 3. Kirim histori ke OpenRouter
            jawaban = await asyncio.to_thread(tanya_openrouter, messages_payload)
            await message.reply(jawaban[:1900])

    await bot.process_commands(message)

# ---------------------------------------------------------
# 5. Slash Commands (`/tanya` & `/cari`)
# ---------------------------------------------------------
@bot.tree.command(name="tanya", description="Tanya apa saja ke Astra (Aman, Santai, Multi-Language)")
@app_commands.describe(
    prompt="Masukkan pertanyaan kamu",
    bahasa="Opsional: Tentukan bahasa jawaban (contoh: English, Sunda, Jawa)"
)
async def slash_tanya(interaction: discord.Interaction, prompt: str, bahasa: Optional[str] = None):
    await interaction.response.defer()
    
    sender_name = interaction.user.display_name
    final_prompt = f"[{sender_name}]: {prompt}"
    
    if bahasa:
        final_prompt += f"\n\n[Instruksi: Berikan jawaban sepenuhnya dalam bahasa {bahasa}]"
        
    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": final_prompt}
    ]
        
    jawaban = await asyncio.to_thread(tanya_openrouter, messages_payload)
    await interaction.followup.send(jawaban[:1900])

@bot.tree.command(name="cari", description="Cari info/berita terbaru dari web via Astra")
@app_commands.describe(
    query="Topik atau pertanyaan yang ingin dicari di web",
    bahasa="Opsional: Tentukan bahasa jawaban (contoh: English, Indonesia)"
)
async def slash_cari(interaction: discord.Interaction, query: str, bahasa: Optional[str] = None):
    await interaction.response.defer()
    
    sender_name = interaction.user.display_name
    web_data = await asyncio.to_thread(cari_web, query)
    
    full_prompt = f"[{sender_name}]: Gunakan data referensi pencarian web berikut untuk menjawab pertanyaan:\n\nHASIL WEB:\n{web_data}\n\nPERTANYAAN: {query}"
    if bahasa:
        full_prompt += f"\n\n[Instruksi: Berikan jawaban sepenuhnya dalam bahasa {bahasa}]"
        
    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": full_prompt}
    ]
        
    jawaban = await asyncio.to_thread(tanya_openrouter, messages_payload)
    await interaction.followup.send(jawaban[:1900])

# ---------------------------------------------------------
# 6. Jalankan Bot
# ---------------------------------------------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
