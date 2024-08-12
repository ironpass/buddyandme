import aiohttp
import os
import io

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = "https://api.openai.com/v1"

AZURE_API_KEY = os.getenv("AZURE_API_KEY")
AZURE_REGION = os.getenv("AZURE_REGION")

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def send_whisper_stt_request(wav_data):
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

async def send_deepgram_stt_request(wav_data):
    deepgram_endpoint = "https://api.deepgram.com/v1/listen"

    headers = {
        'Authorization': f"Token {DEEPGRAM_API_KEY}",
        'Content-Type': 'audio/wav'
    }

    params = {
        'language': 'th',
        'model': 'whisper-large',
    }

    # Using aiohttp to send the POST request
    async with aiohttp.ClientSession() as session:
        async with session.post(
                deepgram_endpoint,
                headers=headers,
                params=params,
                data=wav_data) as response:
            response.raise_for_status()  # Raise an error for bad responses
            result = await response.json()
            transcription = result['results']['channels'][0]['alternatives'][0]['transcript']
            transcription = transcription.replace(" ", "")
            return {"text": transcription}


async def send_azure_stt_request(wav_data):
    # Azure STT endpoint
    azure_endpoint = f"https://{AZURE_REGION}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"

    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_API_KEY,
        'Content-Type': 'audio/wav',
        'Accept': 'application/json'
    }

    params = {
        'language': 'th-TH',
        'profanity': 'raw',   # Options: raw, removed, or masked
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
                azure_endpoint,
                headers=headers,
                params=params,
                data=wav_data) as response:
            response.raise_for_status()
            transcription = await response.json()
            return {"text": transcription["DisplayText"]}
