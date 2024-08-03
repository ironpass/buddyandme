import aiohttp
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = "https://api.openai.com/v1"

async def send_tts_request(gpt_text):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{OPENAI_API_BASE}/audio/speech",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": "tts-1", "voice": "nova", "input": gpt_text, "speed": 0.70, "response_format": "pcm"}) as response:
            response.raise_for_status()
            return await response.read()
