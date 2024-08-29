import aiohttp
import os

# Environment variables for OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = "https://api.openai.com/v1"

# Environment variables for Azure TTS
AZURE_API_KEY = os.getenv("AZURE_API_KEY")
AZURE_REGION = os.getenv("AZURE_REGION")

async def send_openai_tts_request(gpt_text):
    """Send TTS request to OpenAI API."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{OPENAI_API_BASE}/audio/speech",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": "tts-1", "voice": "nova", "input": gpt_text, "speed": 0.75, "response_format": "pcm"}) as response:
            response.raise_for_status()
            return await response.read()

async def send_azure_tts_request(text):
    """Send TTS request to Microsoft Azure TTS API using SSML."""
    azure_endpoint = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"

    # SSML input for Azure TTS
    ssml_text = f"""
    <speak version='1.0' xml:lang='th-TH'>
        <voice name='th-TH-PremwadeeNeural'>
            <prosody rate="-30%" pitch="140%" contour="(50%,+50%) (100%,-100%)">
                {text}
            </prosody>
        </voice>
    </speak>
    """

    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_API_KEY,
        'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': 'raw-24khz-16bit-mono-pcm',
        'User-Agent': 'BUDDYANDME-SERVER'
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(azure_endpoint, headers=headers, data=ssml_text) as response:
            response.raise_for_status()
            return await response.read()
