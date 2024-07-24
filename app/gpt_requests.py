import aiohttp
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = "https://api.openai.com/v1"

async def send_transcription_request(wav_data):
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field('file', wav_data, filename='audio.wav', content_type='audio/wav')
        data.add_field('model', 'whisper-1')
        data.add_field('language', 'th')
        data.add_field('prompt', 'buddy, บั้ดดี้')
        async with session.post(
                f"{OPENAI_API_BASE}/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                data=data) as response:
            response.raise_for_status()
            return await response.json()

async def send_gpt_request(messages):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{OPENAI_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini-2024-07-18", "messages": messages, "max_tokens": 150}) as response:
            response.raise_for_status()
            return await response.json()