import time
import asyncio
from typing import Any, Optional, Dict

import aiohttp
from aiohttp import web
import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import CONFIG
from logger import LOGGER
from limiter import GLOBAL_RATE_LIMITER
from database import QURAN_DB, SURAH_OFFICIAL_NAMES
from search import SmartSearch
from groq_client import GroqClient
from prompt_builder import PromptBuilder

# Clients
from helper import get_tafsir_with_fallback
from hadith_client import HadithClient
from islamic_client import IslamicAPIClient

class IslamicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.groq_client: Optional[GroqClient] = None
        self.hadith_client: Optional[HadithClient] = None
        self.islamic_client: Optional[IslamicAPIClient] = None
        self.user_languages: Dict[int, str] = {}

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.groq_client = GroqClient(self.session)
        self.hadith_client = HadithClient(self.session)
        self.islamic_client = IslamicAPIClient(self.session)
        QURAN_DB.load_data()
        
        try:
            synced = await self.tree.sync()
            LOGGER.info(f"Synced {len(synced)} Slash Commands for Islamic.AI Bot!")
        except Exception as e:
            LOGGER.error(f"Failed to sync slash commands: {e}")

        if not self.keep_alive_ping.is_running():
            self.keep_alive_ping.start()

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

    @tasks.loop(hours=3)
    async def keep_alive_ping(self):
        if CONFIG.STREAMLIT_URL and "streamlit.app" in CONFIG.STREAMLIT_URL and self.session:
            try:
                async with self.session.get(CONFIG.STREAMLIT_URL, timeout=15) as resp:
                    LOGGER.info(f"[Keep-Alive] Ping status: {resp.status}")
            except Exception as e:
                LOGGER.warning(f"[Keep-Alive] Failed: {e}")

    @keep_alive_ping.before_loop
    async def before_keep_alive(self):
        await self.wait_until_ready()

BOT = IslamicBot()

@BOT.event
async def on_ready():
    LOGGER.info(f"Islamic.AI Bot ({BOT.user}) is Online!")
    await BOT.change_presence(activity=discord.Game(name="/help | Authentic Islamic AI"))

@BOT.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = message.content.strip()
    parsed_verse = QURAN_DB.parse_verse_key(content)
    if parsed_verse and len(content.split()) <= 5:
        surah_num, start_a, end_a = parsed_verse
        await send_quran_embed(message.channel, surah_num, start_a, end_a, reply_msg=message)
        return

    is_mentioned = BOT.user in message.mentions
    is_reply_to_bot = False
    
    if message.reference and message.reference.message_id:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg and ref_msg.author == BOT.user:
                is_reply_to_bot = True
        except Exception as e:
            LOGGER.warning(f"Failed to fetch reference message: {e}")

    if is_reply_to_bot or is_mentioned:
        async with message.channel.typing():
            clean_prompt = content.replace(f"<@{BOT.user.id}>", "").replace(f"<@!{BOT.user.id}>", "").strip()
            if not clean_prompt:
                clean_prompt = "Assalamu'alaikum, is there anything you can help me with?"

            raw_history = []
            async for msg in message.channel.history(limit=8):
                h_text = msg.content.replace(f"<@{BOT.user.id}>", "").replace(f"<@!{BOT.user.id}>", "").strip()
                if not h_text:
                    continue
                if msg.author == BOT.user:
                    raw_history.append(f"Assistant: {h_text}")
                elif not msg.author.bot:
                    sender_name = msg.author.display_name
                    raw_history.append(f"User [{sender_name}]: {h_text}")

            raw_history.reverse()
            
            web_ref = await SmartSearch.execute_search(BOT.session, clean_prompt)
            quran_ctx = PromptBuilder.extract_quran_context(clean_prompt)
            
            user_lang = BOT.user_languages.get(message.author.id)
            lang_instruction = PromptBuilder.create_language_instruction(user_lang, clean_prompt)

            prompt = (
                f"{lang_instruction}\n\n"
                f"USER PROMPT: {clean_prompt}\n\n"
                f"VERIFIED WEB REFERENCES:\n{web_ref}\n\n"
                f"{quran_ctx}\n"
                f"CHAT HISTORY:\n" + "\n".join(raw_history) + "\n\n"
                f"[MANDATORY REQUIREMENT: Your answer MUST contain: (1) Relevant Arabic Dalil text + translation grounded in the provided JSON, and (2) Explicit book/scholarly source citations.]\n\n"
                f"REMINDER AGAIN:\n{lang_instruction}"
            )

            jawaban = await BOT.groq_client.chat_completion(
                prompt_text=prompt,
                system_prompt=PromptBuilder.SYSTEM_PROMPT,
                preferred_model=CONFIG.MODEL_HEAVY
            )
            await send_long_message(message, jawaban, mode="reply")
            return

    await BOT.process_commands(message)

async def send_long_message(target: Any, text: str, mode: str = "reply"):
    if not text:
        return
    limit = 1900
    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 > limit:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            if len(p) > limit:
                lines = p.split('\n')
                for line in lines:
                    if len(current_chunk) + len(line) + 1 > limit:
                        chunks.append(current_chunk.strip())
                        current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"
            else:
                current_chunk = p + "\n\n"
        else:
            current_chunk += p + "\n\n"
            
    if current_chunk:
        chunks.append(current_chunk.strip())

    for i, chunk in enumerate(chunks):
        if not chunk: continue
        if mode == "reply":
            if i == 0 and hasattr(target, "reply"):
                await target.reply(chunk)
            else:
                channel = getattr(target, "channel", target)
                await channel.send(chunk)
        elif mode == "slash":
            if hasattr(target, "followup"):
                await target.followup.send(chunk)
            elif hasattr(target, "send_message"):
                await target.send_message(chunk)

async def send_quran_embed(destination: Any, surah_num: int, start_ayah: int, end_ayah: Optional[int] = None, reply_msg: Optional[discord.Message] = None):
    end_v = end_ayah if end_ayah else start_ayah
    verses = QURAN_DB.get_range(surah_num, start_ayah, end_v)

    if not verses:
        msg = f"❌ Verse QS {surah_num}:{start_ayah} not found!"
        if reply_msg:
            await reply_msg.reply(msg)
        elif hasattr(destination, "followup"):
            await destination.followup.send(msg)
        else:
            await destination.send(msg)
        return

    surah_name = verses[0]["surah_name"]
    title_ref = f"📖 QS. {surah_name} ({surah_num}:{start_ayah}" + (f"-{end_v})" if start_ayah != end_v else ")")
    embed = discord.Embed(title=title_ref, color=discord.Color.gold())
    
    arab_texts, trans_texts = [], []
    for v in verses:
        arab_texts.append(f"({v['ayah_num']}) {v['ar']}")
        trans_texts.append(f"**[{v['ayah_num']}]** {v['tr']}")

    embed.add_field(name="Arabic Text (qpc-hafs.json)", value="\n".join(arab_texts)[:1024], inline=False)
    embed.add_field(name="JSON Reference Translation", value="\n".join(trans_texts)[:1024], inline=False)
    embed.set_footer(text="Source: Official Local JSON Database")

    if reply_msg:
        await reply_msg.reply(embed=embed)
    elif hasattr(destination, "followup"):
        await destination.followup.send(embed=embed)
    else:
        await destination.send(embed=embed)

async def process_slash_query(
    interaction: discord.Interaction,
    prompt: str,
    language: Optional[str] = None,
    model_override: str = CONFIG.MODEL_LIGHT,
    command_type: str = "general"
):
    user_id = interaction.user.id
    is_limited, remaining = await GLOBAL_RATE_LIMITER.is_rate_limited(user_id)
    if is_limited:
        await interaction.followup.send(f"⏱️ Please slow down! Try again in {remaining:.1f} seconds.")
        return

    try:
        sender_name = interaction.user.display_name
        web_ref = await SmartSearch.execute_search(BOT.session, prompt)
        quran_ctx = PromptBuilder.extract_quran_context(prompt)
        
        if language:
            BOT.user_languages[user_id] = language
            
        saved_lang = BOT.user_languages.get(user_id)
        lang_instruction = PromptBuilder.create_language_instruction(saved_lang, prompt)

        type_instruction = ""
        if command_type == "hadith":
            type_instruction = "\n\n[STRICT COMMAND MANDATE: HADITH SPECIFIC (/hadith)]\nFocus 100% on Authentic Hadiths across Kutubus Sittah."
        elif command_type == "tafsir":
            type_instruction = "\n\n[STRICT COMMAND MANDATE: TAFSIR SPECIFIC (/tafsir)]\nFocus strictly on Qur'anic exegesis and commentary."
        elif command_type == "fiqh":
            type_instruction = "\n\n[STRICT COMMAND MANDATE: FIQH SPECIFIC (/fiqh)]\nCRITICAL MADHHAB FOCUS: Dedicate 95% of your answer ONLY to the selected perspective without unnecessary tables."
        elif command_type == "dua":
            type_instruction = "\n\n[STRICT COMMAND MANDATE: DUA SPECIFIC (/dua)]\nCRITICAL: Never invent Arabic Duas or book sources. Strictly use provided API texts or known authentic Quranic/Sunnah prayers."

        final_prompt = (
            f"{lang_instruction}\n\n"
            f"USER PROMPT [{sender_name}]: {prompt}\n\n"
            f"VERIFIED SEARCH REFERENCES:\n{web_ref}\n\n"
            f"{quran_ctx}\n"
            f"[MANDATORY REQUIREMENT: Include Arabic Dalil text + book citation.]{type_instruction}\n\n"
            f"REMINDER AGAIN:\n{lang_instruction}"
        )

        jawaban = await BOT.groq_client.chat_completion(
            prompt_text=final_prompt,
            system_prompt=PromptBuilder.SYSTEM_PROMPT,
            preferred_model=model_override
        )
        await send_long_message(interaction, jawaban, mode="slash")
    except Exception as e:
        LOGGER.error(f"Error processing query '{prompt}': {e}")
        await interaction.followup.send(f"⚠️ An error occurred: {e}")


# =========================================================
# COMMANDS
# =========================================================

@BOT.tree.command(name="help", description="Guide & command list")
async def slash_help(interaction: discord.Interaction, language: Optional[str] = None):
    guide_text = "📖 **Islamic.AI — Command Guide**\nUse `/quran`, `/ask`, `/fiqh`, `/hadith`, `/tafsir`, `/dua`, `/asmaulhusna`, `/prophet`, `/prayertimes`, `/dalil`, `/search`, `/ping`."
    if language:
        BOT.user_languages[interaction.user.id] = language
    await interaction.response.send_message(guide_text)

@BOT.tree.command(name="quran", description="Get exact Qur'an Arabic text and translation")
async def slash_quran(interaction: discord.Interaction, surah: int, verse: int, verse_to: Optional[int] = None, language: Optional[str] = None):
    await interaction.response.defer()
    if language:
        BOT.user_languages[interaction.user.id] = language
    await send_quran_embed(interaction, surah, verse, verse_to)

@BOT.tree.command(name="ask", description="Ask anything about Islam")
async def slash_ask(interaction: discord.Interaction, prompt: str, language: Optional[str] = None):
    await interaction.response.defer()
    if language:
        BOT.user_languages[interaction.user.id] = language
    await process_slash_query(interaction, prompt, language, CONFIG.MODEL_HEAVY, command_type="ask")

@BOT.tree.command(name="tafsir", description="Detailed Qur'anic exegesis (with auto-fallback)")
@app_commands.choices(
    source=[
        app_commands.Choice(name="Tafsir Ibn Kathir", value="data/en-tafisr-ibn-kathir.json"),
        app_commands.Choice(name="Tafsir Ma'ariful Qur'an", value="data/en-tafsir-maarif-ul-quran.json"),
        app_commands.Choice(name="Tafsir Al-Jalalayn", value="data/tafsir-al-jalalayn.json")
    ]
)
async def slash_tafsir(
    interaction: discord.Interaction, 
    verse: str, 
    source: Optional[app_commands.Choice[str]] = None, 
    language: Optional[str] = None
):
    await interaction.response.defer()
    
    if language:
        BOT.user_languages[interaction.user.id] = language

    primary_file = source.value if source else "data/en-tafisr-ibn-kathir.json"
    primary_name = source.name if source else "Tafsir Ibn Kathir"
    
    parsed_verse = QURAN_DB.parse_verse_key(verse)
    if parsed_verse:
        surah, start_a, _ = parsed_verse
        verse_key = f"{surah}:{start_a}"
    else:
        verse_key = verse.strip()

    tafsir_text, used_source, is_fallback = get_tafsir_with_fallback(verse_key, primary_file)
    
    if tafsir_text:
        fallback_note = ""
        if is_fallback:
            fallback_note = (
                f"\n[NOTE: The requested Tafsir '{primary_name}' does not have an entry for verse '{verse_key}'. "
                f"I automatically fetched the reference from '{used_source}' as a fallback. Please inform the user gracefully].\n"
            )

        query = (
            f"Provide comprehensive Tafsir for verse '{verse_key}'.\n"
            f"{fallback_note}\n"
            f"TAFSIR REFERENCE DATA ({used_source}):\n{tafsir_text}\n\n"
            f"Please explain and structure this commentary clearly."
        )
    else:
        query = (
            f"User asked for Tafsir for verse '{verse_key}' using {primary_name}. "
            f"However, the specific JSON entry is missing in the local database. Please explain this honestly to the user."
        )
    
    await process_slash_query(interaction, query, language, CONFIG.MODEL_HEAVY, command_type="tafsir")

@BOT.tree.command(name="fiqh", description="Ask Fiqh rulings with Madhhab selection")
@app_commands.choices(
    madhhab=[
        app_commands.Choice(name="Shafi'i", value="shafii"),
        app_commands.Choice(name="Hanafi", value="hanafi"),
        app_commands.Choice(name="Maliki", value="maliki"),
        app_commands.Choice(name="Hanbali", value="hanbali"),
        app_commands.Choice(name="Ja'fari / Shia Twelver", value="jaafari_shia"),
        app_commands.Choice(name="Zaidi / Shia Zaidiyyah", value="zaidi_shia"),
        app_commands.Choice(name="Progressive / Reformist Muslim Thought", value="progressive_muslims"),
        app_commands.Choice(name="Comparative", value="comparative_all")
    ]
)
async def slash_fiqh(interaction: discord.Interaction, question: str, madhhab: Optional[app_commands.Choice[str]] = None, language: Optional[str] = None):
    await interaction.response.defer()
    if language:
        BOT.user_languages[interaction.user.id] = language
        
    chosen_madhhab = madhhab.value if madhhab else "comparative_all"
    query = f"Fiqh Question: '{question}'. Requested Perspective: {chosen_madhhab.upper()}."
    await process_slash_query(interaction, query, language, CONFIG.MODEL_HEAVY, command_type="fiqh")

@BOT.tree.command(name="hadith", description="Search verified Hadiths based on topics and books.")
@app_commands.choices(book=[
    app_commands.Choice(name="Sahih al-Bukhari", value="sahih-bukhari"),
    app_commands.Choice(name="Sahih Muslim", value="sahih-muslim"),
    app_commands.Choice(name="Sunan an-Nasai", value="sunan-an-nasai"),
    app_commands.Choice(name="Sunan Abu Dawud", value="sunan-abu-dawud"),
    app_commands.Choice(name="Jami at-Tirmidhi", value="jami-at-tirmidhi"),
    app_commands.Choice(name="Sunan Ibn Majah", value="sunan-ibn-majah"),
    app_commands.Choice(name="Muwatta Malik", value="muwatta-malik"),
    app_commands.Choice(name="Musnad Ahmad", value="musnad-ahmad"),
])
async def slash_hadith(
    interaction: discord.Interaction, 
    topic: str, 
    book: Optional[app_commands.Choice[str]] = None, 
    language: Optional[str] = None
):
    await interaction.response.defer()
    
    if language:
        BOT.user_languages[interaction.user.id] = language
        
    book_value = book.value if book else None
    book_display_name = book.name if book else "All Major Books"
    
    raw_hadith_data = ""
    try:
        if BOT.hadith_client:
            raw_hadith_data = await BOT.hadith_client.search_hadiths(
                topic=topic, 
                book=book_value
            )
    except Exception as e:
        LOGGER.error(f"Failed to fetch data from hadith_client: {e}")
        raw_hadith_data = "Failed to fetch from API. Please rely on standard knowledge."

    query = (
        f"User is looking for a Hadith about: '{topic}' in book: '{book_display_name}'.\n\n"
        f"HADITHAPI RAW DATA:\n{raw_hadith_data}\n\n"
        f"TASK:\n"
        f"1. Show the original Arabic text.\n"
        f"2. Translate the Hadith, narrator, and meaning matching the user's language.\n"
        f"3. Do NOT hallucinate hadith numbers or text not present in the data."
    )
    
    await process_slash_query(interaction, query, language, CONFIG.MODEL_LIGHT, command_type="hadith")

# =========================================================
# UNIVERSAL ISLAMIC API COMMANDS (islamic_client.py)
# =========================================================

@BOT.tree.command(name="dua", description="Search for authentic Duas from Quran & Sunnah")
async def slash_dua(interaction: discord.Interaction, topic: str, language: Optional[str] = None):
    await interaction.response.defer()
    if language:
        BOT.user_languages[interaction.user.id] = language
    
    raw_data = await BOT.islamic_client.get_dua(topic) if BOT.islamic_client else ""

    query = (
        f"User is searching for a Dua about: '{topic}'.\n\nISLAMICAPI DATA:\n{raw_data}\n\n"
        f"TASK: Show the Arabic text from the data above, then translate the meaning and reference naturally matching the user's input language without hallucinating."
    )
    await process_slash_query(interaction, query, language, CONFIG.MODEL_LIGHT, command_type="dua")

@BOT.tree.command(name="asmaulhusna", description="Learn the 99 Names of Allah (Asmaul Husna)")
async def slash_asmaulhusna(interaction: discord.Interaction, name: str, language: Optional[str] = None):
    await interaction.response.defer()
    if language:
        BOT.user_languages[interaction.user.id] = language
    
    raw_data = await BOT.islamic_client.get_asmaul_husna(name) if BOT.islamic_client else ""
    
    query = (
        f"Explain the Asmaul Husna: '{name}'.\n\nISLAMICAPI DATA:\n{raw_data}\n\n"
        f"TASK: Based on the data, explain the profound meaning and how to apply this attribute in daily life. Match the user's input language."
    )
    await process_slash_query(interaction, query, language, CONFIG.MODEL_LIGHT, command_type="general")

@BOT.tree.command(name="prophet", description="Read the stories and miracles of the Prophets")
async def slash_prophet(interaction: discord.Interaction, prophet_name: str, language: Optional[str] = None):
    await interaction.response.defer()
    if language:
        BOT.user_languages[interaction.user.id] = language
    
    raw_data = await BOT.islamic_client.get_prophet_story(prophet_name) if BOT.islamic_client else ""
    
    query = (
        f"Tell the story of Prophet '{prophet_name}'.\n\nISLAMICAPI DATA:\n{raw_data}\n\n"
        f"TASK: Summarize the story, mention his miracles, and list the wisdom/lessons we can learn. Match the user's input language."
    )
    await process_slash_query(interaction, query, language, CONFIG.MODEL_HEAVY, command_type="general")

@BOT.tree.command(name="prayertimes", description="Check accurate prayer times for your city")
async def slash_prayertimes(interaction: discord.Interaction, city: str, language: Optional[str] = None):
    await interaction.response.defer()
    if language:
        BOT.user_languages[interaction.user.id] = language
    
    raw_data = await BOT.islamic_client.get_prayer_times(city) if BOT.islamic_client else ""
    
    query = (
        f"Show prayer times for city '{city}'.\n\nISLAMICAPI DATA:\n{raw_data}\n\n"
        f"TASK: Present the prayer times (Fajr, Dhuhr, Asr, Maghrib, Isha) neatly using bullet points matching the user's input language."
    )
    await process_slash_query(interaction, query, language, CONFIG.MODEL_LIGHT, command_type="general")

# =========================================================

@BOT.tree.command(name="dalil", description="Find evidence from Qur'an & Sunnah")
async def slash_dalil(interaction: discord.Interaction, topic: str, language: Optional[str] = None):
    await interaction.response.defer()
    if language:
        BOT.user_languages[interaction.user.id] = language
    
    query = f"Provide authentic Dalil for topic: '{topic}'."
    await process_slash_query(interaction, query, language, CONFIG.MODEL_HEAVY, command_type="dalil")

@BOT.tree.command(name="search", description="Search web references")
async def slash_search(interaction: discord.Interaction, query: str, language: Optional[str] = None):
    await interaction.response.defer()
    if language:
        BOT.user_languages[interaction.user.id] = language
        
    await process_slash_query(interaction, query, language, CONFIG.MODEL_LIGHT, command_type="search")

@BOT.tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    latency = round(BOT.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: `{latency}ms`")

async def start_web_server():
    async def handle_ping(request):
        return web.Response(text="Bot is alive!", status=200)

    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", CONFIG.PORT)
    
    try:
        await site.start()
        LOGGER.info(f"Keep-alive web server bound to port {CONFIG.PORT}")
    except OSError as e:
        LOGGER.warning(f"⚠️ Port {CONFIG.PORT} is already in use. Skipping web server! {e}")

async def main():
    if not CONFIG.DISCORD_TOKEN:
        LOGGER.critical("DISCORD_TOKEN missing! Exiting...")
        return
    await start_web_server()
    try:
        await BOT.start(CONFIG.DISCORD_TOKEN)
    except KeyboardInterrupt:
        LOGGER.info("Shutdown requested...")
    finally:
        await BOT.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("Terminated.")
