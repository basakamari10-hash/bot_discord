import os
import discord
from discord.ext import commands
import requests
from duckduckgo_search import DDGS

# Config
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_QURAN")    # Ubah ke DISCORD_TOKEN_QURAN
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_URL = "https://router.huggingface.co/hf-inference/models/mujadid-syahbana/alquran-verse-recitation-wave2vec2-xls-r-model"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

SYSTEM_PROMPT = """
Kamu adalah 'Qur'an Assistant', bot yang dirancang untuk memberikan informasi seputar Al-Qur'an, ayat, terjemahan, dan tafsir secara akurat dan sopan.
Aturan respons:
1. Bersikap sangat sopan, santun, dan objektif.
2. Cantumkan nama Surah dan nomor Ayat jika menyebutkan ayat Al-Qur'an (Contoh: QS. Al-Baqarah: 255).
3. Berikan terjemahan bahasa Indonesia dan inggris yang jelas.
"""

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!quran ", intents=intents)
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

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="!quran tanya | !quran cari"))
    print(f"✅ Bot Quran ({bot.user}) Online!")

@bot.command(name="tanya")
async def tanya(ctx, *, prompt: str):
    async with ctx.typing():
        formatted_prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
        payload = {"inputs": formatted_prompt, "parameters": {"max_new_tokens": 500, "temperature": 0.5, "return_full_text": False}}
        
        try:
            res = requests.post(MODEL_URL, headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                ans = data[0].get("generated_text", "Maaf, tidak ada respon.") if isinstance(data, list) else str(data)
                await ctx.reply(ans[:1900])
            else:
                await ctx.reply("⚠️ AI sedang sibuk, silakan coba lagi.")
        except Exception as e:
            await ctx.reply(f"⚠️ Error: {e}")

@bot.command(name="cari")
async def cari(ctx, *, query: str):
    async with ctx.typing():
        web_data = cari_web(query)
        full_prompt = f"Gunakan data referensi berikut untuk menjawab pertanyaan teologis/ayat:\n\nREFERENSI:\n{web_data}\n\nPERTANYAAN: {query}"
        formatted_prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{full_prompt}<|im_end|>\n<|im_start|>assistant\n"
        payload = {"inputs": formatted_prompt, "parameters": {"max_new_tokens": 600, "temperature": 0.3, "return_full_text": False}}
        
        try:
            res = requests.post(MODEL_URL, headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                ans = data[0].get("generated_text", "Maaf, tidak ada respon.") if isinstance(data, list) else str(data)
                await ctx.reply(ans[:1900])
            else:
                await ctx.reply("⚠️ Gagal mencari referensi.")
        except Exception as e:
            await ctx.reply(f"⚠️ Error: {e}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
