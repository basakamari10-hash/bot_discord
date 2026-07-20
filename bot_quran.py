import os
import discord
from discord import app_commands
from discord.ext import commands
import requests
import streamlit as st
from duckduckgo_search import DDGS

# ---------------------------------------------------------
# 1. Tampilan Dashboard Streamlit
# ---------------------------------------------------------
st.set_page_config(page_title="Bot Quran Discord", page_icon="📖")
st.title("📖 Bot Quran Discord Assistant 24/7")
st.success("🟢 Server Bot Quran (Slash Command) Aktif & Running!")

# ---------------------------------------------------------
# 2. Konfigurasi Token & API
# ---------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_QURAN") or st.secrets.get("DISCORD_TOKEN_QURAN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or st.secrets.get("OPENROUTER_API_KEY")

MODEL_NAME = "nvidia/nemotron-3-ultra-550b-a55b:free"

SYSTEM_PROMPT = """
Kamu adalah 'Qur'an Assistant', bot yang dirancang untuk memberikan informasi seputar Al-Qur'an, ayat, terjemahan, dan tafsir secara akurat dan sopan.
Aturan respons:
1. Bersikap sangat sopan, santun, dan objektif.
2. Cantumkan nama Surah dan nomor Ayat jika menyebutkan ayat Al-Qur'an (Contoh: QS. Al-Baqarah: 255).
3. Berikan terjemahan bahasa Indonesia dan inggris yang jelas.
"""

# ---------------------------------------------------------
# 3. Inisialisasi Bot Discord
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True  # Wajib ON di Discord Developer Portal
bot = commands.Bot(command_prefix="!", intents=intents)

def tanya_openrouter(system_prompt, user_prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 1000
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
            res = ddgs.text(f"quran tafsir ayat {query}", max_results=3)
            for r in res:
                results.append(f"Judul: {r['title']}\nIsi: {r['body']}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Gagal pencarian web: {e}"

# ---------------------------------------------------------
# 4. Event: Auto Sync Slash Command & Auto Reply Listener
# ---------------------------------------------------------
@bot.event
async def on_ready():
    # Mendaftarkan Slash Command ke Discord
    try:
        synced = await bot.tree.sync()
        print(f"✅ Berhasil mendaftarkan {len(synced)} Slash Commands!")
    except Exception as e:
        print(f"❌ Gagal sync slash commands: {e}")
        
    await bot.change_presence(activity=discord.Game(name="/tanya | /cari atau Reply pesan ini"))
    print(f"✅ Bot Quran ({bot.user}) Online & Siap Digunakan!")

@bot.event
async def on_message(message):
    # Abaikan jika pesan dari bot sendiri
    if message.author.bot:
        return

    is_reply_to_bot = False
    # Cek apakah pengguna membalas (reply) pesan bot
    if message.reference and message.reference.message_id:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.author == bot.user:
                is_reply_to_bot = True
        except Exception:
            pass

    # Cek apakah bot di-mention/tag (@Bot)
    is_mentioned = bot.user in message.mentions

    # Jika pesan adalah reply ke bot atau bot di-mention
    if is_reply_to_bot or is_mentioned:
        async with message.channel.typing():
            # Hapus teks tag/mention dari pesan agar bersih
            clean_text = message.content.replace(f"<@{bot.user.id}>", "").strip()
            if clean_text:
                jawaban = tanya_openrouter(SYSTEM_PROMPT, clean_text)
                await message.reply(jawaban[:1900])
            else:
                await message.reply("Ada yang bisa saya bantu terkait Al-Qur'an?")

    await bot.process_commands(message)

# ---------------------------------------------------------
# 5. Slash Commands (`/tanya` & `/cari`)
# ---------------------------------------------------------
@bot.tree.command(name="tanya", description="Tanya seputar Al-Qur'an, tafsir, dan terjemahan")
@app_commands.describe(prompt="Masukkan pertanyaan kamu")
async def slash_tanya(interaction: discord.Interaction, prompt: str):
    # Defer dulu agar Discord tidak komplain jika AI butuh waktu berpikir
    await interaction.response.defer()
    jawaban = tanya_openrouter(SYSTEM_PROMPT, prompt)
    await interaction.followup.send(jawaban[:1900])

@bot.tree.command(name="cari", description="Cari referensi/tafsir ayat Al-Qur'an via Web")
@app_commands.describe(query="Topik atau ayat yang ingin dicari")
async def slash_cari(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    web_data = cari_web(query)
    full_prompt = f"Gunakan data referensi berikut untuk menjawab pertanyaan teologis/ayat:\n\nREFERENSI:\n{web_data}\n\nPERTANYAAN: {query}"
    jawaban = tanya_openrouter(SYSTEM_PROMPT, full_prompt)
    await interaction.followup.send(jawaban[:1900])

# ---------------------------------------------------------
# 6. Jalankan Bot
# ---------------------------------------------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
