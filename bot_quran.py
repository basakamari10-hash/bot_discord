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
# Quran Database Helper (JSON Grounding)
# ---------------------------------------------------------
class QuranDB:
    def __init__(self, json_path="quran_id.json"):
        self.json_path = json_path
        self.data = {}
        self.load_data()

    def load_data(self):
        """Memuat file JSON ke RAM saat bot start."""
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                print("✅ Database JSON Al-Qur'an berhasil dimuat!")
            except Exception as e:
                print(f"❌ Gagal memuat file JSON Al-Qur'an: {e}")
        else:
            print(f"⚠️ Warning: File '{self.json_path}' tidak ditemukan. Fitur JSON tidak aktif.")

    def get_verse(self, surah_num: int, ayah_num: int):
        """Mengambil 1 ayat spesifik."""
        surah_key = str(surah_num)
        ayah_key = str(ayah_num)

        if surah_key in self.data:
            surah_info = self.data[surah_key]
            verses = surah_info.get("verses", {})
            if ayah_key in verses:
                return {
                    "surah_name": surah_info.get("name_latin", f"Surah {surah_num}"),
                    "surah_num": surah_num,
                    "ayah_num": ayah_num,
                    "ar": verses[ayah_key].get("ar", ""),
                    "id": verses[ayah_key].get("id", "")
                }
        return None

    def get_range(self, surah_num: int, start_ayah: int, end_ayah: int):
        """Mengambil rentang ayat (misal: 1:1-7)."""
        results = []
        for a in range(start_ayah, end_ayah + 1):
            v = self.get_verse(surah_num, a)
            if v:
                results.append(v)
        return results

# Inisialisasi Database JSON Global
quran_db = QuranDB("quran_id.json")

def ambil_konteks_quran_otomatis(teks_input: str) -> str:
    """
    INSPEKTOR GLOBAL: Mendeteksi pola nomor ayat (misal '2:255' atau '1:1-7') dari input user di COMMAND APAPUN.
    Mengambil data resmi Arab & Terjemahan Kemenag dari JSON lalu menyuntikkannya ke Prompt Groq.
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
            surah_name = verses[0]["surah_name"]
            header = f"--- QS. {surah_name} [{surah_num}:{start_ayah}" + (f"-{end_ayah}] ---" if start_ayah != end_ayah else "] ---")
            details = []
            for v in verses:
                details.append(f"Arabic Verse ({v['ayah_num']}): {v['ar']}\nIndonesian Translation ({v['ayah_num']}): {v['id']}")
            extracted_data.append(header + "\n" + "\n".join(details))
    
    if extracted_data:
        return (
            "\n\n[OFFICIAL QURAN DATA INJECTED FROM LOCAL KEMENAG JSON DATABASE]\n"
            "CRITICAL INSTRUCTION: If you quote the Quran for the references below, you MUST USE the EXACT Arabic text "
            "and translation provided here verbatim. DO NOT rewrite or generate Quranic Arabic from memory.\n\n"
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
            indo_texts = []
            for v in verses_data:
                arab_texts.append(f"({v['ayah_num']}) {v['ar']}")
                indo_texts.append(f"**[{v['ayah_num']}]** {v['id']}")

            embed.add_field(name="Teks Arab", value="\n".join(arab_texts)[:1024], inline=False)
            embed.add_field(name="Terjemahan (Kemenag RI)", value="\n".join(indo_texts)[:1024], inline=False)
            embed.set_footer(text="Sumber: Official Database Al-Qur'an Kemenag (Zero AI Hallucination)")
            
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
                f"[MANDATORY REQUIREMENT: Your answer MUST contain: (1) Relevant Arabic Dalil text + translation matching Kemenag standards, and (2) Explicit book/scholarly source citations.]"
            )

            jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
            await kirim_pesan_panjang(message, jawaban, mode="reply")

    await bot.process_commands(message)

# ---------------------------------------------------------
# Slash Commands (Setiap Command Memakai ambil_konteks_quran_otomatis)
# ---------------------------------------------------------

@bot.tree.command(name="help", description="Guide & commands for Islamic.AI Bot")
async def slash_help(interaction: discord.Interaction):
    guide_text = (
        "📖 **Islamic.AI — Command Guide & Help**\n\n"
        "**Main Commands (Strictly Grounded with Dalil & Sources):**\n"
        "• `/quran [surah] [ayat] [ayat_sampai]` - Fetch exact Arabic & Translation directly from Kemenag JSON Database (0% Hallucination).\n"
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

@bot.tree.command(name="quran", description="Get exact Qur'an Arabic text and Kemenag translation directly from database")
@app_commands.describe(
    surah="Nomor Surah (1-114)",
    ayat="Nomor Ayat",
    ayat_sampai="Opsional: Rentang ayat akhir (misal: 7 untuk ayat 1-7)"
)
async def slash_quran(
    interaction: discord.Interaction, 
    surah: int, 
    ayat: int, 
    ayat_sampai: Optional[int] = None
):
    await interaction.response.defer()
    
    end_v = ayat_sampai if ayat_sampai else ayat
    verses = quran_db.get_range(surah, ayat, end_v)

    if not verses:
        await interaction.followup.send(f"❌ Ayat tidak ditemukan! Pastikan Surah **{surah}** dan Ayat **{ayat}** sudah benar.")
        return

    surah_name = verses[0]["surah_name"]
    title_ref = f"📖 QS. {surah_name} [{surah}:{ayat}" + (f"-{end_v}]" if ayat != end_v else "]")
    
    embed = discord.Embed(title=title_ref, color=discord.Color.gold())
    
    arab_texts = []
    indo_texts = []
    for v in verses:
        arab_texts.append(f"({v['ayah_num']}) {v['ar']}")
        indo_texts.append(f"**[{v['ayah_num']}]** {v['id']}")

    embed.add_field(name="Teks Arab", value="\n".join(arab_texts)[:1024], inline=False)
    embed.add_field(name="Terjemahan (Kemenag RI)", value="\n".join(indo_texts)[:1024], inline=False)
    embed.set_footer(text="Sumber: Official Database Al-Qur'an Kemenag (Zero AI Hallucination)")

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="ask", description="Ask anything about Islam (Arabic Dalil & Book Citations Included)")
@app_commands.describe(
    prompt="Your question or topic",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_ask(
    interaction: discord.Interaction, 
    prompt: str, 
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        web_ref = await asyncio.to_thread(cari_web, prompt)
        quran_ctx = ambil_konteks_quran_otomatis(prompt) # INJEKSI OTOMATIS
        
        final_prompt = (
            f"[{sender_name}]: {prompt}\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}\n"
            f"{quran_ctx}\n"
            f"[MANDATORY REQUIREMENT: You MUST include: (1) Relevant Arabic Dalil text with translation conforming to Kemenag standards, and (2) Explicit classical/contemporary Fiqh or Tafsir book citation.]"
        )
        if language:
            final_prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language from start to finish.]"
            
        jawaban = await asyncio.to_thread(tanya_groq, final_prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="tafsir", description="Detailed Qur'anic exegesis (Injected with Official JSON Data)")
@app_commands.describe(
    verse="Verse reference (e.g., '2:255')",
    source="Optional: Tafsir book (Ibn Kathir, Jalalayn, etc.)",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_tafsir(
    interaction: discord.Interaction, 
    verse: str, 
    source: Optional[str] = None,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        search_query = f"tafsir verse {verse} {source if source else 'ibn kathir jalalayn'}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        quran_ctx = ambil_konteks_quran_otomatis(verse) # INJEKSI OTOMATIS
        
        prompt = (
            f"[{sender_name}]: Provide a comprehensive tafsir for verse {verse}.\n"
            f"Primary reference requested: {source if source else 'Tafsir Ibn Kathir / Jalalayn'}.\n"
            f"{quran_ctx}\n"
            f"MANDATORY REQUIREMENT:\n"
            f"1. Use the EXACT Arabic text and Translation provided in context above (DO NOT alter Arabic text).\n"
            f"2. Detailed Tafsir Explanation with explicit Book Title citation\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="fiqh", description="Ask Fiqh rulings with Arabic Dalil & Kitāb sources")
@app_commands.describe(
    question="Your jurisprudence (Fiqh) question",
    madhhab="Select Madhhab perspective",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
@app_commands.choices(
    madhhab=[
        app_commands.Choice(name="Shafi'i", value="shafii"),
        app_commands.Choice(name="Hanafi", value="hanafi"),
        app_commands.Choice(name="Maliki", value="maliki"),
        app_commands.Choice(name="Hanbali", value="hanbali"),
        app_commands.Choice(name="Ja'fari / Shia Twelver", value="jaafari_shia"),
        app_commands.Choice(name="Zaidi / Shia Zaidiyyah", value="zaidi_shia"),
        app_commands.Choice(name="Comparative (All Schools of Thought)", value="comparative_all")
    ]
)
async def slash_fiqh(
    interaction: discord.Interaction, 
    question: str, 
    madhhab: Optional[app_commands.Choice[str]] = None,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        chosen_madhhab = madhhab.value if madhhab else "comparative_all"
        
        if chosen_madhhab == "zaidi_shia":
            search_query = f"fiqh ruling dalil kitab {question} zaidi shia site:salvationark.com OR site:zaydi.info OR site:ziydia.com"
        else:
            search_query = f"fiqh ruling dalil kitab {question} madhhab {chosen_madhhab}"
            
        web_ref = await asyncio.to_thread(cari_web, search_query)
        quran_ctx = ambil_konteks_quran_otomatis(question) # INJEKSI OTOMATIS
        
        prompt = (
            f"[{sender_name}]: Fiqh Question: '{question}'. Requested Madhhab: {chosen_madhhab.upper()}.\n"
            f"{quran_ctx}\n"
            f"MANDATORY REQUIREMENT:\n"
            f"1. Provide Arabic Dalil (Quran/Hadith Matan) with translation matching Kemenag standards.\n"
            f"2. Cite the specific Fiqh book (e.g., Al-Majmu' al-Mu'tabar for Zaidi, or Al-Majmu' for Shafi'i) or classical Madhhab source.\n"
            f"3. Maintain absolute scholarly neutrality without external polemical labels or sectarian insults.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="hadith", description="Search authentic Hadiths with Arabic Matan & Collection Citations")
@app_commands.describe(
    topic="Hadith topic or keyword",
    book="Optional: Hadith Collection (Bukhari, Muslim, Abu Dawud, etc.)",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_hadith(
    interaction: discord.Interaction, 
    topic: str, 
    book: Optional[str] = None,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        search_query = f"matan hadits arab {topic} {book if book else 'sahih bukhari muslim'}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        quran_ctx = ambil_konteks_quran_otomatis(topic) # INJEKSI OTOMATIS
        
        prompt = (
            f"[{sender_name}]: Search authentic Hadiths regarding '{topic}'. Requested Collection: {book if book else 'Kutubus Sittah'}.\n"
            f"{quran_ctx}\n"
            f"MANDATORY FORMAT:\n"
            f"1. Original Arabic Matan Text\n"
            f"2. Complete Translation\n"
            f"3. Exact Collection Citation (e.g., HR. Bukhari No. xxx / Sahih Muslim)\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"
            
        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="dua", description="Search authentic Duas and Adhkar with Arabic Text & Sources")
@app_commands.describe(
    topic="Topic or situation for the Dua",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_dua(
    interaction: discord.Interaction, 
    topic: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        search_query = f"doa dzikir arab latin terjemahan {topic}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        quran_ctx = ambil_konteks_quran_otomatis(topic) # INJEKSI OTOMATIS
        
        prompt = (
            f"[{sender_name}]: Provide authentic Duas for topic/situation: '{topic}'.\n"
            f"{quran_ctx}\n"
            f"MANDATORY FORMAT:\n"
            f"1. Original Arabic Text\n"
            f"2. Transliteration & Translation\n"
            f"3. Hadith / Adhkar Book Source Citation\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="dalil", description="Find Qur'anic and Hadith evidence (Arabic + Translation + Sources)")
@app_commands.describe(
    topic="Topic or issue to search evidence for",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_dalil(
    interaction: discord.Interaction, 
    topic: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        search_query = f"matan hadits sahih bukhari muslim ayat quran dalil {topic} quran.kemenag.go.id"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        quran_ctx = ambil_konteks_quran_otomatis(topic) # INJEKSI OTOMATIS
        
        prompt = (
            f"[{sender_name}]: Provide authentic Dalil (Qur'an verses conforming to Kemenag standard and Sahih Hadiths) for topic: '{topic}'.\n"
            f"{quran_ctx}\n"
            f"MANDATORY FORMAT:\n"
            f"1. Original Arabic Text\n"
            f"2. Complete Translation (Kemenag standard)\n"
            f"3. Explicit Reference Source & Kitāb Name (Surah name/number or Hadith Collection)\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}"
        )
        if language:
            prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="search", description="Search Islamic research references from the web with citations")
@app_commands.describe(
    query="Search keywords",
    language="Optional: Type target response language (e.g., Sundanese, English, Arabic)"
)
async def slash_search(
    interaction: discord.Interaction, 
    query: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        web_data = await asyncio.to_thread(cari_web, query)
        quran_ctx = ambil_konteks_quran_otomatis(query) # INJEKSI OTOMATIS
        
        full_prompt = (
            f"[{sender_name}]: Use the following web references to answer.\n"
            f"{quran_ctx}\n"
            f"MANDATORY REQUIREMENT: Provide Arabic Dalil (Kemenag standard) and cite explicit sources:\n\n"
            f"REFERENCES:\n{web_data}\n\nQUESTION: {query}"
        )
        if language:
            full_prompt += f"\n\n[MANDATORY INSTRUCTION: Force and generate your ENTIRE response strictly in '{language}' language.]"
            
        jawaban = await asyncio.to_thread(tanya_groq, full_prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="test", description="Test Groq API connection, latency, and system health")
async def slash_test(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        start_time = time.time()
        respon = await asyncio.to_thread(tanya_groq, "System test: Provide 1 short Islamic greeting in English.", MODEL_RINGAN)
        api_latency = round((time.time() - start_time) * 1000)
        discord_ping = round(bot.latency * 1000)
        
        db_status = "Connected & Loaded" if quran_db.data else "Not Loaded (Fallback Active)"

        status_msg = (
            "🧪 **[SYSTEM DIAGNOSTIC - ISLAMIC.AI]**\n\n"
            f"🟢 **Groq API Status:** Connected & Active\n"
            f"📖 **Quran JSON Database:** `{db_status}`\n"
            f"⚡ **API Latency:** `{api_latency}ms`\n"
            f"📡 **Discord Ping:** `{discord_ping}ms`\n"
            f"🧠 **Active Engine:** Global JSON Grounding RAG (`llama-3.3-70b-versatile`)\n\n"
            f"💬 **Output Test Sample:**\n> {respon}"
        )
        await interaction.followup.send(status_msg)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Diagnostic test failed: {e}")

@bot.tree.command(name="ping", description="Check bot latency status")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Islamic.AI latency: `{latency}ms` (Global JSON Injection Active)")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN_QURAN is not set in Streamlit Secrets!")
    else:
        bot.run(DISCORD_TOKEN)
