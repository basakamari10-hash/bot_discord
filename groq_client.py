import re
import asyncio
import aiohttp
from config import CONFIG
from logger import LOGGER

class GroqClient:
    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    @staticmethod
    def clean_repetition(text: str) -> str:
        if not text:
            return ""
        pattern = r'(\b[\w\u0600-\u06FF\u0100-\u024F]+\b)(?:\s+\1){3,}'
        return re.sub(pattern, r'\1', text, flags=re.IGNORECASE).strip()

    async def chat_completion(
        self,
        prompt_text: str,
        system_prompt: str,
        preferred_model: str = CONFIG.MODEL_LIGHT
    ) -> str:
        if not CONFIG.GROQ_API_KEY:
            return "❌ Groq API key is not configured. Please set GROQ_API_KEY."

        headers = {
            "Authorization": f"Bearer {CONFIG.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        model_chain = [preferred_model]
        for m in [CONFIG.MODEL_HEAVY, CONFIG.MODEL_LIGHT, CONFIG.MODEL_FALLBACK]:
            if m not in model_chain:
                model_chain.append(m)

        for model_name in model_chain:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ],
                "temperature": 0.0,
                "max_tokens": 3000
            }

            for attempt in range(CONFIG.MAX_RETRIES):
                try:
                    async with self.session.post(
                        self.API_URL,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=CONFIG.REQUEST_TIMEOUT)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            raw_content = data['choices'][0]['message']['content']
                            return self.clean_repetition(raw_content)
                        elif resp.status in (429, 500, 502, 503, 504):
                            LOGGER.warning(f"Groq API HTTP {resp.status} on {model_name}, retrying...")
                            await asyncio.sleep((2 ** attempt) + 0.5)
                            continue
                        else:
                            LOGGER.warning(f"Groq API Error {resp.status}: {await resp.text()}")
                            break
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    LOGGER.warning(f"Groq Connection error ({e}) on model {model_name}")
                    await asyncio.sleep((2 ** attempt) + 0.5)

        return "⚠️ Sorry, all Groq AI servers are currently busy. Please try again in a few moments."
