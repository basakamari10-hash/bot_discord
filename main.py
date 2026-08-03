import sys
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

# Import modul internal
from config import CONFIG
from logger import LOGGER
from limiter import GLOBAL_RATE_LIMITER
from cache import GLOBAL_CACHE
from prompt_builder import PromptBuilder
from search import SmartSearch
from hadith_client import HadithAPIClient
from groq_client import GroqClient

# Setup Bot Discord
intents = discord.Intents.default()
intents.message_content = True

class IslamicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.session: aiohttp.ClientSession = None
        self.search_engine: SmartSearch = None
        self.hadith_api: HadithAPIClient = None
        self.groq_client: GroqClient = None

    async def setup_hook(self):
        # Inisialisasi HTTP Session global untuk performa async yang stabil
        self.session = aiohttp.ClientSession()
        self.search_engine = SmartSearch()
        self.hadith_api = HadithAPIClient(self.session)
        self.groq_client = GroqClient(self.session)
        
        LOGGER.info("Menyinkronkan Slash Commands ke Discord...")
        await self.tree.sync()

    async def close(self):
        # Cleanup session saat bot mati
        if self.session and not self.session.closed:
            await self.session.close()
        await super().close()

bot = IslamicBot()

# ---------------------------------------------------------
# Helper: Pemotong Pesan (Discord Limit 2000 Karakter)
# ---------------------------------------------------------
async def send_split_message(interaction: discord.Interaction, text: str):
    """Memotong teks jika melebihi batas 2000 karakter Discord."""
    if len(text) <= 2000:
        await interaction.followup.send(text)
        return

    # Potong berdasarkan paragraf atau baris
    chunks = []
    while len(text) > 2000:
        split_pos = text.rfind("\n", 0, 1900)
        if split_pos == -1:
            split_pos = 1900
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip()
    chunks.append(text)

    for i, chunk in enumerate(chunks):
        if i == 0:
            await interaction.followup.send(chunk)
        else:
            await interaction.channel.send(chunk)

# ---------------------------------------------------------
# Discord Events
# ---------------------------------------------------------
@bot.event
async def on_ready():
    LOGGER.info(f"✅ Bot Berhasil Online! Logged in as: {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Game(name="/ask | /hadith | /quran — Islamic AI Assistant")
    )

# ---------------------------------------------------------
# Slash Commands
# ---------------------------------------------------------

# 1. Command /ask (Pertanyaan Umum & Fiqh dengan RAG Web Search)
@bot.tree.command(name="ask", description="Tanya seputar Al-Qur'an, Fiqh, Hadits, dan Studi Islam")
@app_commands.describe(pertanyaan="Ketik pertanyaanmu di sini...")
async def ask_command(interaction: discord.Interaction, pertanyaan: str):
    user_id = interaction.user.id
    
    # Check Rate Limit / Cooldown
    is_limited, retry_after = await GLOBAL_RATE_LIMITER.is_rate_limited(user_id)
    if is_limited:
        await interaction.response.send_message(
            f"⏳ Mohon tunggu {retry_after:.1f} detik sebelum menggunakan perintah lagi.",
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    # 1. Cek Cache terlebih dahulu
    cache_key = f"ask:{pertanyaan.strip().lower()}"
    cached_reply = await GLOBAL_CACHE.get(cache_key)
    if cached_reply:
        await send_split_message(interaction, cached_reply)
        return

    # 2. Cari konteks via RAG Web Search
    search_context = await bot.search_engine.search_web(pertanyaan)

    # 3. Rakit Prompt & panggil LLM
    system_prompt = PromptBuilder.build_system_prompt()
    user_prompt = PromptBuilder.build_user_prompt(
        user_query=pertanyaan,
        search_context=search_context
    )

    reply = await bot.groq_client.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )

    # 4. Simpan ke Cache & Kirim Pesan
    await GLOBAL_CACHE.set(cache_key, reply)
    await send_split_message(interaction, reply)


# 2. Command /hadith (Pencarian Spesifik via HadithAPI.com)
@bot.tree.command(name="hadith", description="Cari Hadits Shahih berdasarkan kata kunci atau topik")
@app_commands.describe(topik="Misal: niat, shalat, ramadhan, atau nomor hadits")
async def hadith_command(interaction: discord.Interaction, topik: str):
    user_id = interaction.user.id

    is_limited, retry_after = await GLOBAL_RATE_LIMITER.is_rate_limited(user_id)
    if is_limited:
        await interaction.response.send_message(
            f"⏳ Mohon tunggu {retry_after:.1f} detik.",
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    cache_key = f"hadith:{topik.strip().lower()}"
    cached_reply = await GLOBAL_CACHE.get(cache_key)
    if cached_reply:
        await send_split_message(interaction, cached_reply)
        return

    # 1. Tarik data dari HadithAPI.com
    hadith_context = await bot.hadith_api.search_hadith(query=topik)

    # 2. Rakit Prompt dengan Konteks Hadits Terverifikasi
    system_prompt = PromptBuilder.build_system_prompt()
    user_prompt = PromptBuilder.build_user_prompt(
        user_query=f"Jelaskan dan uraikan hadits mengenai topik: {topik}",
        search_context=hadith_context
    )

    reply = await bot.groq_client.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )

    await GLOBAL_CACHE.set(cache_key, reply)
    await send_split_message(interaction, reply)

# ---------------------------------------------------------
# Main Execution Runner
# ---------------------------------------------------------
async def main():
    token = CONFIG.DISCORD_TOKEN
    if not token:
        LOGGER.critical("❌ ERROR: DISCORD_TOKEN tidak ditemukan di Environment/Secrets!")
        sys.exit(1)

    try:
        await bot.start(token)
    except KeyboardInterrupt:
        LOGGER.info("Bot dihentikan secara manual.")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
