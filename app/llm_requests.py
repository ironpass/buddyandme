import aiohttp
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = "https://api.openai.com/v1"

async def send_gpt_request(messages):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{OPENAI_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini-2024-07-18", "messages": messages}) as response:
            response.raise_for_status()
            json_response = await response.json()
            return json_response["choices"][0]["message"]["content"].strip()


from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

async def send_groq_request(messages):
    messages = [
        {key: value for key, value in message.items() if key != "timestamp"} for message in messages
    ]
    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama3-groq-70b-8192-tool-use-preview",
    )
    return chat_completion.choices[0].message.content.strip()
    