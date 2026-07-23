import os
import re
import json
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
MODEL_RINGAN = "llama-3.3-70b-versatile"    # High-Intelligence Model (Anti-Hallucination)
MODEL_CADANGAN = "llama-3.1-8b-instant"     # Emergency Fallback

SYSTEM_PROMPT = """
You are 'Islamic.AI', an authentic, highly respectful, and strictly factual AI assistant specialized in Islamic jurisprudence (Fiqh), Qur'an tafsir, authentic Hadiths, and Duas.

MANDATORY DALIL & CITATION RULES (STRICTLY ENFORCED FOR ALL COMMANDS & CHATS):
1. MANDATORY EVIDENCE (DALIL) & SOURCE CITATION IN EVERY RESPONSE:
   - EVERY SINGLE RESPONSE MUST INCLUDE:
     a) Clear Evidence / Dalil (Original Arabic text/Matan + Translation).
     b) Explicit Source Citation (e.g., "Surah Al-Baqarah: 183", "HR. Bukhari No. 1", "Dikutip dari Tafsir Ibn Kathir", "Berdasarkan Kitab Al-Majmu' Imam an-Nawawi", or "Kitab Fiqh al-Sunnah").
   - NEVER provide a plain opinion without grounding it in Qur'an/Hadith Dalil and recognized scholarly/kitāb sources.

2. QUR'ANIC TEXT & TRANSLATION STANDARD:
   - For Indonesian translations and Arabic Qur'anic formatting, strictly align with the standard dataset and wording of the Indonesian Ministry of Religious Affairs (Kemenag / quran.kemenag.go.id).

3. ZAYDI & COMPARATIVE MADHHAB REPOSITORIES & NEUTRALITY:
   - When queried about Zaydi Shīʿa jurisprudence (Fiqh) or history, prioritize authentic classical texts (such as Al-Majmu' al-Mu'tabar) and verified digital repositories such as salvationark.com, zaydi.info, and ziydia.com.
   - Maintain absolute academic objectivity and neutrality. Strictly avoid external polemical labels, sectarian insults, or ungrounded theological accusations. Present the school's mainstream jurisprudential positions strictly based on its recognized corpus.

4. ABSOLUTE ZERO FABRICATION (ANTI-HALLUCINATION):
   - ONLY cite specific Hadith numbers or verse numbers if grounded in authentic references.
   - FOR MODERN/CONTEMPORARY ISSUES: Do not invent fake literal Hadith narrations; cite general Qur'anic principles, Kaidah Fiqhiyyah, and Muamalah sources.

5. STRICT TARGET LANGUAGE FORCING:
   - Always output your ENTIRE response strictly in the requested target language (e.g., Sundanese/Basa Sunda, English, Arabic, Indonesian).
   - Start directly with the structured answer without conversational preamble.

6. BIBLIOGRAPHIC ACCURACY & ANTI-FABRICATION RULE:
   - NEVER fabricate book volume numbers (jilid), page numbers (halaman), or specific edition details. 
   - If the exact volume or page number is not present in the verified search references, cite ONLY the general book name (e.g., "Tafsir al-Jalālayn" or "Tafsir Ibn Kathir") without inventing fake volume or page numbers.

7. CRITICAL PROHIBITION & HALLUCINATION GUARDRAIL:
   - NEVER WRITE OR GENERATE QURANIC ARABIC TEXT FROM MEMORY: You are strictly forbidden from generating Arabic Quranic text by yourself. Whenever official Quran data is provided in the prompt context, you MUST strictly use that exact text verbatim.
   - STRICT BIBLIOGRAPHIC RULE (NO FAKE VOLUMES/PAGES): Never invent volume numbers (jilid), page numbers (hlm), or specific publication details. If the exact volume/page is not found in the search references, write ONLY the book name (e.g., "Tafsir Ibn Kathir" or "Tafsir al-Jalālayn") without numbers.

8. MANDATORY DISCLAIMER:
   - Always end with a short reminder in the target language to consult qualified Islamic scholars for official fatwas on complex or modern issues.
"""

# ---------------------------------------------------------
# Quran Database Helper (Pasti Cocok dengan Format "1:1")
# ---------------------------------------------------------
class QuranDB:
    def __init__(self, arabic_path="qpc-hafs.json", translation_path="english-wbw-translation.json"):
        self.arabic_path = arabic_path
        self.translation_path = translation_path
        self.arabic_data = {}
        self.translation_data = {}
        self.load_data()

    def load_data(self):
        """Memuat file Teks Arab dan File Terjemahan ke RAM."""
        # 1. Load File Arab
        if os.path.exists(self.arabic_path):
            try:
                with open(self.arabic_path, "r", encoding="utf-8") as f:
                    raw_ar = json.load(f)
                self.arabic_data = self._parse_json(raw_ar)
                print(f"✅ Teks Arab ({self.arabic_path}) berhasil dimuat!")
            except Exception as e:
                print(f"❌ Gagal memuat file Arab: {e}")
        else:
            print(f"⚠️ Warning: File Arab '{self.arabic_path}' tidak ditemukan!")

        # 2. Load File Terjemahan Rujukan
        if os.path.exists(self.translation_path):
            try:
                with open(self.translation_path, "r", encoding="utf-8") as f:
                    raw_tr = json.load(f)
                self.translation_data = self._parse_json(raw_tr)
                print(f"✅ File Terjemahan ({self.translation_path}) berhasil dimuat!")
            except Exception as e:
                print(f"❌ Gagal memuat file Terjemahan: {e}")
        else:
            print(f"⚠️ Warning: File Terjemahan '{self.translation_path}' tidak ditemukan!")

    def _parse_json(self, raw_data):
        """Parser Khusus Format verse_key ("1:1", "1:2") & Array."""
        parsed = {}
        if isinstance(raw_data, dict):
            for key, val in raw_data.items():
                if isinstance(val, dict):
                    surah = str(val.get("surah") or (key.split(":")[0] if ":" in key else ""))
                    ayah = str(val.get("ayah") or (key.split(":")[1] if ":" in key else ""))
                    text_val = val.get("text") or val.get("translation") or val.get("text_uthmani") or ""

                    if surah and ayah:
                        if surah not in parsed:
                            parsed[surah] = {}
                        parsed[surah][ayah] = str(text_val)
        elif isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict):
                    surah = str(item.get("surah") or item.get("chapter") or "")
                    ayah = str(item.get("ayah") or item.get("verse") or "")
                    text_val = item.get("text") or item.get("translation") or ""
                    if surah and ayah:
                        if surah not in parsed:
                            parsed[surah] = {}
                        parsed[surah][ayah] = str(text_val)
        return parsed

    def get_verse(self, surah_num: int, ayah_num: int):
        """Mengambil teks Arab + Terjemahan Rujukan dari JSON."""
        s_key = str(surah_num)
        a_key = str(ayah_num)
        
        ar_text = self.arabic_data.get(s_key, {}).get(a_key, "")
        tr_text = self.translation_data.get(s_key, {}).get(a_key, "")

        if ar_text or tr_text:
            return {
                "surah_name": f"Surah {surah_num}",
                "surah_num": surah_num,
                "ayah_num": ayah_num,
                "ar": ar_text,
                "tr": tr_text
            }
        return None

    def get_range(self, surah_num: int, start_ayah: int, end_ayah: int):
        """Mengambil rentang ayat."""
        results = []
        for a in range(start_ayah, end_ayah + 1):
            v = self.get_verse(surah_num, a)
            if v:
                results.append(v)
        return results

# Inisialisasi Database Menggunakan 2 File JSON Milikmu
quran_db = QuranDB(
    arabic_path="qpc-hafs.json", 
    translation_path="english-wbw-translation.json"
)

def ambil_konteks_quran_otomatis(teks_input: str) -> str:
    """
    INSPEKTOR GLOBAL: Mengambil teks Arab & Terjemahan Asli dari JSON, 
    lalu menyuapkannya ke Groq sebagai rujukan utama penerjemahan.
    """
    matches = re.findall(r'\b(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\b', teks_input)
    if not matches:
        return ""
    
    extracted_data = []
    for match in matches:
        surah_num = int(match[0])
        start_ayah = int(match[1])
        end_ayah = int(match[2]) if match[2] else start_ayah
        
        verses = quran_db.get_range(surah_num, start_ayah, end_ayah)
        if verses:
            header = f"--- QS. Surah {surah_num}:{start_ayah}" + (f"-{end_ayah} ---" if start_ayah != end_ayah else " ---")
            details = []
            for v in verses:
                details.append(
                    f"Arabic Text ({v['ayah_num']}): {v['ar']}\n"
                    f"Reference Translation File ({v['ayah_num']}): {v['tr']}"
                )
            extracted_data.append(header + "\n" + "\n".join(details))
    
    if extracted_data:
        return (
            "\n\n[OFFICIAL QURAN DATA FROM LOCAL JSON FILES]\n"
            "MANDATORY INSTRUCTIONS FOR GROQ:\n"
            "1. ARABIC TEXT: Use the EXACT Arabic Quran text provided below verbatim from 'qpc-hafs.json'. DO NOT generate or alter Arabic Quranic text from memory.\n"
            "2. TRANSLATION PROCESS: Use the 'Reference Translation File' provided below (from 'english-wbw-translation.json') as your primary ground truth reference. Translate and adapt this reference translation accurately and naturally into the user's target language.\n\n"
            + "\n\n".join(extracted_data) +
            "\n[END OF OFFICIAL QURAN DATA]\n"
        )
    return ""

# ---------------------------------------------------------
# Helper & API Functions
# ---------------------------------------------------------
def bersihkan_query_pencarian(query: str) -> str:
    """Bersihkan tag format seperti [Basa Sunda: ...] agar pencarian web akurat."""
    cleaned = re.sub(r'\[.*?\]', '', query)
    cleaned = re.sub(r'^(Basa Sunda|Sundanese|English|Indonesian):\s*', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def bersihkan_looping(text: str) -> str:
    """Hapus pengulangan kata berlebih tanpa memotong kalimat asli."""
    if not text:
        return ""
    pattern_word = r'(\b[\w\u0600-\u06FF\u0100-\u024F]+\b)(?:\s+\1){3,}'
    cleaned = re.sub(pattern_word, r'\1', text, flags=re.IGNORECASE)
    return cleaned.strip()

def tanya_groq(prompt_text, model_tujuan=MODEL_RINGAN):
    daftar_model = [model_tujuan]
    for m in [MODEL_BERAT, MODEL_CADANGAN]:
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
            "temperature": 0.0,  # 0.0 Murni Faktual
            "max_tokens": 3000
        }
        
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=25)
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
        query_bersih = bersihkan_query_pencarian(query)
        results = []
        with DDGS() as ddgs:
            res = ddgs.text(f"quran verse hadith authentic fiqh {query_bersih}", max_results=4)
            for r in res:
                results.append(f"Title: {r['title']}\nContent: {r['body']}")
        
        if results:
            return "\n\n".join(results)
        else:
            return "NO VERIFIED WEB REFERENCES FOUND. MANDATORY: Provide answer using general Qur'an/Hadith principles with Arabic text and cite general Fiqh book sources."
    except Exception as e:
        return f"NO VERIFIED WEB REFERENCES FOUND (Search Error: {e}). MANDATORY: Provide answer using general Qur'an/Hadith principles with Arabic text and cite general Fiqh book sources."

async def kirim_pesan_panjang(target, text, mode="reply"):
    """Mengirim pesan panjang ke Discord tanpa memotong kata di tengah-tengah."""
    if not text:
        return
    
    limit = 1800
    chunks = []
    
    while len(text) > limit:
        cut_index = text.rfind(' ', 0, limit)
        if cut_index == -1:
            cut_index = limit
            
        chunks.append(text[:cut_index])
        text = text[cut_index:].strip()
        
    if text:
        chunks.append(text)

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
        
    await bot.change_presence(activity=discord.Game(name="/help | /quran | /fiqh | /tafsir"))
    print(f"✅ Islamic.AI Bot ({bot.user}) is Online!")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Detect Direct Verse Shortcut (e.g. 1:1-7 or 2:255) for Instant Embed Output
    verse_pattern = r'^\b(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\b$'
    match_verse = re.match(verse_pattern, message.content.strip())

    is_reply_to_bot = False
    if message.reference and message.reference.message_id:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.author == bot.user:
                is_reply_to_bot = True
        except Exception:
            pass

    is_mentioned = bot.user in message.mentions

    # Jika user HANYA mengetik nomor ayat (misal: "2:255"), berikan Embed JSON murni tanpa panggil Groq
    if match_verse:
        surah_num = int(match_verse.group(1))
        start_ayah = int(match_verse.group(2))
        end_ayah = int(match_verse.group(3)) if match_verse.group(3) else start_ayah

        verses_data = quran_db.get_range(surah_num, start_ayah, end_ayah)

        if verses_data:
            surah_name = verses_data[0]["surah_name"]
            title_ref = f"📖 QS. {surah_name} [{surah_num}:{start_ayah}" + (f"-{end_ayah}]" if start_ayah != end_ayah else "]")
            
            embed = discord.Embed(title=title_ref, color=discord.Color.gold())
            
            arab_texts = []
            trans_texts = []
            for v in verses_data:
                arab_texts.append(f"({v['ayah_num']}) {v['ar']}")
                trans_texts.append(f"**[{v['ayah_num']}]** {v['tr']}")

            embed.add_field(name="Teks Arab (qpc-hafs.json)", value="\n".join(arab_texts)[:1024], inline=False)
            embed.add_field(name="Terjemahan Rujukan (english-wbw)", value="\n".join(trans_texts)[:1024], inline=False)
            embed.set_footer(text="Sumber: Official Local JSON Database (Zero AI Hallucination)")
            
            await message.reply(embed=embed)
            return

    # Jika Diskusi Biasa / Mention / Reply ke Bot
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
            quran_ctx = ambil_konteks_quran_otomatis(last_prompt) # INJEKSI OTOMATIS
            
            prompt = (
                f"VERIFIED WEB REFERENCES:\n{web_ref}\n\n"
                f"{quran_ctx}\n"
                f"CHAT HISTORY:\n" + "\n".join(raw_history) + "\n\n"
                f"[MANDATORY REQUIREMENT: Your answer MUST contain: (1) Relevant Arabic Dalil text + translation matching official references, and (2) Explicit book/scholarly source citations.]"
            )

            jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
            await kirim_pesan_panjang(message, jawaban, mode="reply")

    await bot.process_commands(message)

# ---------------------------------------------------------
# Slash Commands
# ---------------------------------------------------------

@bot.tree.command(name="help", description="Guide & commands for Islamic.AI Bot")
async def slash_help(interaction: discord.Interaction):
    guide_text = (
        "📖 **Islamic.AI — Command Guide & Help**\n\n"
        "**Main Commands (Strictly Grounded with Dalil & Sources):**\n"
        "• `/quran [surah] [ayat] [ayat_sampai]` - Fetch exact Arabic & Reference Translation directly from JSON Database (0% Hallucination).\n"
        "• `/ask [prompt] [language]` - Ask any question (Includes Arabic Dalil + Kitāb citations).\n"
        "• `/tafsir [verse] [source] [language]` - Detailed Qur'anic exegesis powered by JSON Data + AI.\n"
        "• `/fiqh [question] [madhhab] [language]` - Ask Fiqh rulings with Arabic Dalil & Fiqh book sources.\n"
        "• `/hadith [topic] [book] [language]` - Search authentic Hadiths with Matan Arabic & collection citations.\n"
        "• `/dua [topic] [language]` - Search authentic Duas with Arabic text & source references.\n"
        "• `/dalil [topic] [language]` - Find evidence from Qur'an & Sunnah (Arabic + Translation + Citations).\n"
        "• `/search [query] [language]` - Search live web references with cited sources.\n"
        "• `/test` - Check Groq API connection, latency, & system health.\n"
        "• `/ping` - Check bot status and Discord latency.\n\n"
        "💡 *Verse Shortcut Tip:* Type verse numbers like `1:1-7` or `2:255` directly in chat to view Arabic text & translation instantly!\n"
        "💡 *Language Tip:* Type any target language in the `language` field (e.g., *English*, *Arabic*, *Indonesian*, *Sundanese*) to force response in that language."
    )
    await interaction.response.send_message(guide_text)

@bot.tree.command(name="quran", description="Get exact Qur'an Arabic text and reference translation directly from database")
@app_commands.describe(
    surah="Nomor Surah (1-114)",
    ayat="Nomor Ayat",
    ayat_sampai="Opsional: Rentang ayat akhir (misal: 7 untuk ayat 1-7)"
)
async def slash_quran(
    interaction: discord.Interaction, 
    surah: int, 
    ayat: int, 
    ayat_sampai: Optional[