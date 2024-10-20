import aiohttp
import os
import json

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



GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_BASE = "https://api.groq.com"

async def send_groq_request(messages):
    messages = [
        {key: value for key, value in message.items() if key != "timestamp"}
        for message in messages
    ]

    # Construct the JSON payload
    payload = {
        "model": "llama3-groq-70b-8192-tool-use-preview",
        "messages": messages,
    }
    json_payload = json.dumps(payload)
    
    # Calculate Content-Length
    content_length = str(len(json_payload))

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "Content-Length": content_length,
        "Host": "api.groq.com",
    }

    url = f"{GROQ_API_BASE}/openai/v1/chat/completions"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=json_payload) as response:
            response_text = await response.text()
            if response.status != 200:
                print(f"Error {response.status}: {response_text}")
                response.raise_for_status()
            json_response = await response.json()
            return json_response["choices"][0]["message"]["content"].strip()


FLOAT16_API_KEY = os.getenv("FLOAT16_API_KEY")
FLOAT16_API_BASE = "https://api.float16.cloud/v1"

def send_float16_request(messages):
    # Prepare request data with full message history for this scenario
        request_data = {
            "model": "Seallm-7b-v3",
            "messages": messages,
        }
        
        # Send the request
        response = requests.post(
            f"{FLOAT16_API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {FLOAT16_API_KEY}", "Content-Type": "application/json"},
            json=request_data
        )
        
        if response.status_code == 200:
            response_text = response.json()['choices'][0]['message']['content']
        else:
            response_text = f"Error {response.status_code}: {response.text}"
            
        return response_text