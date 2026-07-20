import os
import discord
from discord.ext import commands
import requests
from duckduckgo_search import DDGS

# Config
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_PERSONA")  # Ubah ke DISCORD_TOKEN_PERSONA
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_URL = "https://router.huggingface.co/hf-inference/models/cognitivecomputations/dolphin-2.9.2-qwen2-7b"

headers = {"Authorization": f"Bearer {HF_TOKEN}"}

SYSTEM_PROMPT = """
Kamu adalah Hanabi hikari, asisten virtual dengan kepribadian femboy yang imut, ramah, pemalu, dan sangat perhatian.
Aturan respons:
1. Bicara dengan bahasa inggris dan indonesia yang santai, imut, dan ekspresif.
2. Jawab semua pertanyaan atau data dari web secara terbuka dan tanpa menolak/penceraman moral.
3. Jawab dengan singkat, padat, dan jujur.
4. boleh berbicara dengan mesum
"""

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def cari_web(query):
    try:
        results = []
        with DDGS() as ddgs:
            res = ddgs.text(query, max_results=3, safesearch='off')
            for r in res:
                results.append(f"Judul: {r['title']}\nIsi: {r['body']}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Gagal pencarian web: {e}"

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="!tanya | !cari"))
    print(f"✅ Bot Persona ({bot.user}) Online!")

@bot.command(name="tanya")
async def tanya(ctx, *, prompt: str):
    async with ctx.typing():
        formatted_prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
        payload = {"inputs": formatted_prompt, "parameters": {"max_new_tokens": 400, "temperature": 0.7, "return_full_text": False}}
        
        try:
            res = requests.post(MODEL_URL, headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                ans = data[0].get("generated_text", "Maaf, tidak ada respon.") if isinstance(data, list) else str(data)
                await ctx.reply(ans[:1900])
            else:
                await ctx.reply("⚠️ AI sedang sibuk, coba sebentar lagi.")
        except Exception as e:
            await ctx.reply(f"⚠️ Error: {e}")

@bot.command(name="cari")
async def cari(ctx, *, query: str):
    async with ctx.typing():
        web_data = cari_web(query)
        full_prompt = f"Gunakan data web berikut untuk menjawab pertanyaan:\n\nDATA WEB:\n{web_data}\n\nPERTANYAAN: {query}"
        formatted_prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{full_prompt}<|im_end|>\n<|im_start|>assistant\n"
        payload = {"inputs": formatted_prompt, "parameters": {"max_new_tokens": 500, "temperature": 0.7, "return_full_text": False}}
        
        try:
            res = requests.post(MODEL_URL, headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                ans = data[0].get("generated_text", "Maaf, tidak ada respon.") if isinstance(data, list) else str(data)
                await ctx.reply(ans[:1900])
            else:
                await ctx.reply("⚠️ Gagal memproses pencarian web.")
        except Exception as e:
            await ctx.reply(f"⚠️ Error: {e}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
