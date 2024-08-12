import aiohttp
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = "https://api.openai.com/v1"


async def send_gpt_request(messages):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{OPENAI_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini-2024-07-18", "messages": messages, "max_tokens": 150}) as response:
            response.raise_for_status()
            return await response.json()
