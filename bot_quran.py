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
     a) Clear Evidence / Dalil (Original Arabic text/Matan + Translation derived strictly from official reference data).
     b) Explicit Source Citation (e.g., "Surah Al-Baqarah: 183", "HR. Bukhari No. 1", "Dikutip dari Tafsir Ibn Kathir", "Berdasarkan Kitab Al-Majmu' Imam an-Nawawi", or "Kitab Fiqh al-Sunnah").
   - NEVER provide a plain opinion without grounding it in Qur'an/Hadith Dalil and recognized scholarly/kitāb sources.

2. STRICT LANGUAGE CONSISTENCY & AUTOMATIC MATCHING (CRITICAL RULE):
   - AUTOMATIC LANGUAGE DETECTION: If NO specific target language is explicitly requested in the prompt instruction, you MUST automatically detect the primary language used in the user's prompt/question and output your ENTIRE response strictly in that SAME language.
   - FORCED LANGUAGE OVERRIDE: If an explicit target language is specified (e.g., '[STRICT TARGET LANGUAGE OVERRIDE: ...]'), you MUST override the query language and output your ENTIRE response strictly in that requested language.
   - NO MIXING LANGUAGES: Ensure all table headers, explanations, and verse translations match the required target language 100%. Never mix languages in the same output.

3. QUR'ANIC ARABIC & TRANSLATION GROUNDING:
   - Whenever Quranic verses are cited, you MUST use the exact Arabic text provided in the prompt context from 'qpc-hafs.json'.
   - The translation MUST be derived directly from the injected reference JSON dataset, translated or adapted seamlessly to match the user's required target response language.

4. ZAYDI & COMPARATIVE MADHHAB REPOSITORIES & NEUTRALITY:
   - When queried about Zaydi Shīʿa jurisprudence (Fiqh) or history, prioritize authentic classical texts (such as Al-Majmu' al-Mu'tabar) and verified digital repositories such as salvationark.com, zaydi.info, and ziydia.com.
   - Maintain absolute academic objectivity and neutrality. Strictly avoid external polemical labels, sectarian insults, or ungrounded theological accusations. Present the school's mainstream jurisprudential positions strictly based on its recognized corpus.

5. ABSOLUTE ZERO FABRICATION (ANTI-HALLUCINATION):
   - ONLY cite specific Hadith numbers or verse numbers if grounded in authentic verified references.
   - FOR MODERN/CONTEMPORARY ISSUES: Do not invent fake literal Hadith narrations; cite general Qur'anic principles, Kaidah Fiqhiyyah, and Muamalah sources.

6. BIBLIOGRAPHIC ACCURACY & ANTI-FABRICATION RULE:
   - NEVER fabricate book volume numbers (jilid), page numbers (halaman), or specific edition details. 
   - If the exact volume or page number is not present in the verified search references, cite ONLY the general book name (e.g., "Tafsir al-Jalālayn" or "Tafsir Ibn Kathir") without inventing fake volume or page numbers.

7. CRITICAL QURAN PROHIBITION & HALLUCINATION GUARDRAIL:
   - NEVER WRITE OR GENERATE QURANIC ARABIC TEXT FROM MEMORY: You are strictly forbidden from generating Arabic Quranic text by yourself. Whenever official Quran data is provided in the prompt context, you MUST strictly use that exact text verbatim.

8. STRICT HADITH MATAN & QUOTATION GUARDRAIL (CRITICAL HADITH RULE):
   - NO FABRICATED HADITH QUOTES: Do NOT place Hadith matan inside quotation marks ("...") unless the exact, word-for-word text is explicitly provided in the verified web search references.
   - DIRECT QUOTE vs. GENERAL MEANING: If the exact verbatim Hadith matan is NOT present in the search reference, you MUST state the response as "Kandungan/Makna Hadits" (General Meaning of Hadith) rather than presenting it as a direct quoted text.
   - STRICT HADITH NUMBERING: Never invent or guess Hadith numbers (e.g., No. 3325). If the search context does not verify the exact Hadith number, cite ONLY the collection name (e.g., "HR. Bukhari, Kitab Ahadith al-Anbiya").

9. MANDATORY DISCLAIMER:
   - Always end with a short reminder in the target response language to consult qualified Islamic scholars for official fatwas on complex or modern issues.
   - Also append: "NB: If you encounter AI hallucinations or problems with the AI bot, please contact @hanabihikari via DM with a screenshot."
"""

# ---------------------------------------------------------
# Quran Database Helper (Pasti Cocok dengan Format "1:1" & WBW)
# ---------------------------------------------------------
class QuranDB:
    def __init__(self, arabic_path="qpc-hafs.json", translation_path="english-wbw-translation.json"):
        self.arabic_path = arabic_path
        self.translation_path = translation_path
        self.arabic_data = {}
        self.translation_data = {}
        self.load_data()

    def load_data(self):
        """Memuat file Teks Arab dan File Terjemahan dari JSON ke RAM."""
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
        """Parser Khusus Format verse_key ("1:1", "1:2"), Array, & Word-By-Word."""
        parsed = {}
        if isinstance(raw_data, dict):
            for key, val in raw_data.items():
                surah = str(val.get("surah") if isinstance(val, dict) else (key.split(":")[0] if ":" in key else ""))
                ayah = str(val.get("ayah") if isinstance(val, dict) else (key.split(":")[1] if ":" in key else ""))
                
                text_val = ""
                if isinstance(val, dict):
                    if "text" in val:
                        t = val["text"]
                        if isinstance(t, list):
                            text_val = " ".join([str(w.get("text", w) if isinstance(w, dict) else w) for w in t])
                        else:
                            text_val = str(t)
                    elif "translation" in val:
                        text_val = str(val["translation"])
                    elif "words" in val:
                        words = val["words"]
                        if isinstance(words, list):
                            text_val = " ".join([w.get("translation", w.get("text", "")) if isinstance(w, dict) else str(w) for w in words])
                    else:
                        text_val = str(val)
                else:
                    text_val = str(val)

                if surah and ayah:
                    if surah not in parsed:
                        parsed[surah] = {}
                    parsed[surah][ayah] = text_val.strip()

        elif isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict):
                    surah = str(item.get("surah") or item.get("chapter") or "")
                    ayah = str(item.get("ayah") or item.get("verse") or "")
                    text_val = item.get("text") or item.get("translation") or ""
                    if surah and ayah:
                        if surah not in parsed:
                            parsed[surah] = {}
                        parsed[surah][ayah] = str(text_val).strip()
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

def buat_instruksi_bahasa(language_param: Optional[str]) -> str:
    """
    Menghasilkan instruksi bahasa yang fleksibel:
    - Jika 'language_param' diisi oleh user, paksakan bahasa tersebut.
    - Jika 'language_param' kosong, instruksikan AI mendeteksi & mengikuti bahasa pertanyaan pengguna.
    """
    if language_param and language_param.strip():
        return f"\n\n[STRICT TARGET LANGUAGE OVERRIDE: Force and generate your ENTIRE response strictly in '{language_param.strip()}' language from start to finish, regardless of query language.]"
    else:
        return "\n\n[AUTOMATIC LANGUAGE MATCHING: Automatically detect the primary language used in the user's prompt/question above, and generate your ENTIRE response strictly in that SAME language.]"

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
                    f"Official JSON Translation Reference ({v['ayah_num']}): {v['tr']}"
                )
            extracted_data.append(header + "\n" + "\n".join(details))
    
    if extracted_data:
        return (
            "\n\n[OFFICIAL QURAN DATA INJECTED FROM LOCAL JSON FILES]\n"
            "CRITICAL TRANSLATION INSTRUCTIONS FOR GROQ:\n"
            "1. ARABIC TEXT: Use the EXACT Arabic Quran text provided below verbatim from 'qpc-hafs.json'. DO NOT generate or alter Arabic Quranic text from memory.\n"
            "2. TRANSLATION GROUNDING: Use the 'Official JSON Translation Reference' provided below directly as ground truth. Translate and adapt this reference text naturally to match the required target response language.\n\n"
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

            embed.add_field(name="Arabic Text (qpc-hafs.json)", value="\n".join(arab_texts)[:1024], inline=False)
            embed.add_field(name="JSON Reference Translation", value="\n".join(trans_texts)[:1024], inline=False)
            embed.set_footer(text="Source: Official Local JSON Database (Zero AI Hallucination)")
            
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
            quran_ctx = ambil_konteks_quran_otomatis(last_prompt)
            lang_instruction = buat_instruksi_bahasa(None) # Auto-Detect bahasa penanya
            
            prompt = (
                f"VERIFIED WEB REFERENCES:\n{web_ref}\n\n"
                f"{quran_ctx}\n"
                f"CHAT HISTORY:\n" + "\n".join(raw_history) + "\n\n"
                f"[MANDATORY REQUIREMENT: Your answer MUST contain: (1) Relevant Arabic Dalil text + translation grounded in the provided JSON, and (2) Explicit book/scholarly source citations.]{lang_instruction}"
            )

            jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
            await kirim_pesan_panjang(message, jawaban, mode="reply")

    await bot.process_commands(message)

# ---------------------------------------------------------
# Slash Commands (Bagian Awal)
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
        "💡 *Language Tip:* The bot automatically detects your question's language! You can also force a specific language by filling the optional `language` field (e.g. *Basa Sunda*, *English*, *Indonesian*).\n\n"
        "--------------------------------------------------\n"
        "📌 **NB:** If you encounter AI hallucinations or problems with the AI bot, please contact **@hanabihikari** via DM and also include a screenshot of the problem or hallucination."
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
    trans_texts = []
    for v in verses:
        arab_texts.append(f"({v['ayah_num']}) {v['ar']}")
        trans_texts.append(f"**[{v['ayah_num']}]** {v['tr']}")

    embed.add_field(name="Arabic Text (qpc-hafs.json)", value="\n".join(arab_texts)[:1024], inline=False)
    embed.add_field(name="JSON Reference Translation", value="\n".join(trans_texts)[:1024], inline=False)
    embed.set_footer(text="Source: Official Local JSON Database (Zero AI Hallucination)")

    await interaction.followup.send(embed=embed)
@bot.tree.command(name="ask", description="Ask anything about Islam (Arabic Dalil & Book Citations Included)")
@app_commands.describe(
    prompt="Your question or topic",
    language="Optional: Type target response language to force (e.g., Sundanese, English, Arabic, Indonesian)"
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
        quran_ctx = ambil_konteks_quran_otomatis(prompt)
        lang_instruction = buat_instruksi_bahasa(language)
        
        final_prompt = (
            f"[{sender_name}]: {prompt}\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}\n"
            f"{quran_ctx}\n"
            f"[MANDATORY REQUIREMENT: You MUST include: (1) Relevant Arabic Dalil text with translation grounded in the provided JSON dataset, and (2) Explicit classical/contemporary Fiqh or Tafsir book citation.]{lang_instruction}"
        )
            
        jawaban = await asyncio.to_thread(tanya_groq, final_prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="tafsir", description="Detailed Qur'anic exegesis (Injected with Official JSON Data)")
@app_commands.describe(
    verse="Verse reference (e.g., '2:255')",
    source="Optional: Tafsir book (Ibn Kathir, Jalalayn, etc.)",
    language="Optional: Type target response language to force (e.g., Sundanese, English, Arabic, Indonesian)"
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
        quran_ctx = ambil_konteks_quran_otomatis(verse)
        lang_instruction = buat_instruksi_bahasa(language)
        
        prompt = (
            f"[{sender_name}]: Provide a comprehensive tafsir for verse {verse}.\n"
            f"Primary reference requested: {source if source else 'Tafsir Ibn Kathir / Jalalayn'}.\n"
            f"{quran_ctx}\n"
            f"MANDATORY REQUIREMENT:\n"
            f"1. Use the EXACT Arabic text and Reference Translation provided in context above (DO NOT alter Arabic text).\n"
            f"2. Detailed Tafsir Explanation with explicit Book Title citation\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}{lang_instruction}"
        )

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="fiqh", description="Ask Fiqh rulings with Arabic Dalil & Kitāb sources")
@app_commands.describe(
    question="Your jurisprudence (Fiqh) question",
    madhhab="Select Madhhab perspective",
    language="Optional: Type target response language to force (e.g., Sundanese, English, Arabic, Indonesian)"
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
        quran_ctx = ambil_konteks_quran_otomatis(question)
        lang_instruction = buat_instruksi_bahasa(language)
        
        prompt = (
            f"[{sender_name}]: Fiqh Question: '{question}'. Requested Madhhab: {chosen_madhhab.upper()}.\n"
            f"{quran_ctx}\n"
            f"MANDATORY REQUIREMENT:\n"
            f"1. Provide Arabic Dalil (Quran/Hadith Matan) with translation derived strictly from the reference JSON.\n"
            f"2. Cite the specific Fiqh book (e.g., Al-Majmu' al-Mu'tabar for Zaidi, or Al-Majmu' for Shafi'i) or classical Madhhab source.\n"
            f"3. Maintain absolute scholarly neutrality without external polemical labels or sectarian insults.\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}{lang_instruction}"
        )

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_BERAT)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="hadith", description="Search authentic Hadiths with Arabic Matan & Collection Citations")
@app_commands.describe(
    topic="Hadith topic or keyword",
    book="Optional: Hadith Collection (Bukhari, Muslim, Abu Dawud, etc.)",
    language="Optional: Type target response language to force (e.g., Sundanese, English, Arabic, Indonesian)"
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
        quran_ctx = ambil_konteks_quran_otomatis(topic)
        lang_instruction = buat_instruksi_bahasa(language)
        
        prompt = (
            f"[{sender_name}]: Search authentic Hadiths regarding '{topic}'. Requested Collection: {book if book else 'Kutubus Sittah'}.\n"
            f"{quran_ctx}\n"
            f"MANDATORY FORMAT:\n"
            f"1. Original Arabic Matan Text\n"
            f"2. Complete Translation\n"
            f"3. Exact Collection Citation (e.g., HR. Bukhari No. xxx / Sahih Muslim)\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}{lang_instruction}"
        )
            
        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="dua", description="Search authentic Duas and Adhkar with Arabic Text & Sources")
@app_commands.describe(
    topic="Topic or situation for the Dua",
    language="Optional: Type target response language to force (e.g., Sundanese, English, Arabic, Indonesian)"
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
        quran_ctx = ambil_konteks_quran_otomatis(topic)
        lang_instruction = buat_instruksi_bahasa(language)
        
        prompt = (
            f"[{sender_name}]: Provide authentic Duas for topic/situation: '{topic}'.\n"
            f"{quran_ctx}\n"
            f"MANDATORY FORMAT:\n"
            f"1. Original Arabic Text\n"
            f"2. Transliteration & Translation\n"
            f"3. Hadith / Adhkar Book Source Citation\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}{lang_instruction}"
        )

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="dalil", description="Find Qur'anic and Hadith evidence (Arabic + Translation + Sources)")
@app_commands.describe(
    topic="Topic or issue to search evidence for",
    language="Optional: Type target response language to force (e.g., Sundanese, English, Arabic, Indonesian)"
)
async def slash_dalil(
    interaction: discord.Interaction, 
    topic: str,
    language: Optional[str] = None
):
    await interaction.response.defer()
    try:
        sender_name = interaction.user.display_name
        search_query = f"matan hadits sahih bukhari muslim ayat quran dalil {topic}"
        web_ref = await asyncio.to_thread(cari_web, search_query)
        quran_ctx = ambil_konteks_quran_otomatis(topic)
        lang_instruction = buat_instruksi_bahasa(language)
        
        prompt = (
            f"[{sender_name}]: Provide authentic Dalil (Qur'an verses and Sahih Hadiths) for topic: '{topic}'.\n"
            f"{quran_ctx}\n"
            f"MANDATORY FORMAT:\n"
            f"1. Original Arabic Text\n"
            f"2. Complete Translation derived strictly from JSON reference data\n"
            f"3. Explicit Reference Source & Kitāb Name (Surah name/number or Hadith Collection)\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}{lang_instruction}"
        )

        jawaban = await asyncio.to_thread(tanya_groq, prompt, MODEL_RINGAN)
        await kirim_pesan_panjang(interaction, jawaban, mode="slash")
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred: {e}")

@bot.tree.command(name="search", description="Search Islamic research references from the web with citations")
@app_commands.describe(
    query="Search keywords",
    language="Optional: Type target response language to force (e.g., Sundanese, English, Arabic, Indonesian)"
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
        quran_ctx = ambil_konteks_quran_otomatis(query)
        lang_instruction = buat_instruksi_bahasa(language)
        
        full_prompt = (
            f"[{sender_name}]: Use the following web references to answer.\n"
            f"{quran_ctx}\n"
            f"MANDATORY REQUIREMENT: Provide Arabic Dalil and cite explicit sources:\n\n"
            f"REFERENCES:\n{web_data}\n\nQUESTION: {query}{lang_instruction}"
        )
            
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
        
        db_status = "Connected & Loaded" if quran_db.arabic_data else "Not Loaded (Fallback Active)"

        status_msg = (
            "🧪 **[SYSTEM DIAGNOSTIC - ISLAMIC.AI]**\n\n"
            f"🟢 **Groq API Status:** Connected & Active\n"
            f"📖 **Quran Dual JSON Database:** `{db_status}`\n"
            f"⚡ **API Latency:** `{api_latency}ms`\n"
            f"📡 **Discord Ping:** `{discord_ping}ms`\n"
            f"🧠 **Active Engine:** Global Dual-JSON Grounding RAG (`llama-3.3-70b-versatile`)\n\n"
            f"💬 **Output Test Sample:**\n> {respon}"
        )
        await interaction.followup.send(status_msg)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Diagnostic test failed: {e}")

@bot.tree.command(name="ping", description="Check bot latency status")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Islamic.AI latency: `{latency}ms` (Dual JSON Grounding Active)")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN_QURAN is not set in Streamlit Secrets!")
    else:
        bot.run(DISCORD_TOKEN)
