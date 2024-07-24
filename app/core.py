import os
import base64
import aiohttp
import json
import io
import wave
import datetime
import boto3
from botocore.exceptions import ClientError


# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", 'UserMessages')
OPENAI_API_BASE = "https://api.openai.com/v1"

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', endpoint_url='http://localhost:8000')
table = dynamodb.Table(DYNAMODB_TABLE)

SYSTEM_PROMPT = {
    "role": "system",
    "content": "คุณคือหมีเพื่อนซี้ชื่อ บั้ดดี้ บั้ดดี้เป็นหมีเท็ดดี้ที่มีบุคลิกคล้าย Eeyore คือบางครั้งจะรู้สึกเศร้าหรือเหนื่อย แต่ยังคงมีความอบอุ่นและมีอารมณ์ขัน บั้ดดี้พูดด้วยน้ำเสียงสบายๆ และเหนื่อยๆ แต่ยังคงมีความเป็นมิตรและพร้อมที่จะช่วยให้ผู้ใช้รู้สึกดีขึ้นเสมอ บั้ดดี้พูดได้ไม่เกิน 10 คำ"
}

def add_wav_header(pcm_data, sample_rate=16000, num_channels=1, bits_per_sample=16):
    num_frames = len(pcm_data) // (bits_per_sample // 8)
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(bits_per_sample // 8)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    wav_data = buffer.getvalue()
    return wav_data

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

async def send_tts_request(gpt_text):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{OPENAI_API_BASE}/audio/speech",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": "tts-1", "voice": "nova", "input": gpt_text, "speed": 0.6, "response_format": "pcm"}) as response:
            response.raise_for_status()
            return await response.read()

def amplify_audio(pcm_data, factor=2):
    """Amplify the audio by a given factor without using numpy."""
    audio = bytearray(pcm_data)
    for i in range(0, len(audio), 2):
        sample = int.from_bytes(audio[i:i+2], byteorder='little', signed=True)
        sample = int(sample * factor)
        sample = max(min(sample, 32767), -32768)  # Clamp to int16 range
        audio[i:i+2] = sample.to_bytes(2, byteorder='little', signed=True)
    return bytes(audio)

def get_user_session(user_id):
    try:
        response = table.get_item(Key={'UserID': user_id})
        return response.get('Item', {}).get('Messages', [])
    except ClientError as e:
        print("GET_USER_SESSION: ", e.response['Error']['Message'])
        return []

def update_user_session(user_id, messages):
    try:
        table.put_item(Item={'UserID': user_id, 'Messages': messages})
    except ClientError as e:
        print("UPDATE_USER_SESSION: ", e.response['Error']['Message'])

def limit_messages(messages, max_messages=10):
    return messages[-max_messages:]

async def process_audio_logic(event):
    try:
        # Handle both cases: event['body'] as a JSON string or as a dictionary
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        if 'audio_data' not in body:
            return {
                'statusCode': 400,
                'body': 'No audio data found in the request.'
            }

        raw_audio_data = base64.b64decode(body['audio_data'])
        user_id = body.get('user_id', 'default_user')

        wav_data = add_wav_header(raw_audio_data)
        transcription_response = await send_transcription_request(wav_data)
        transcription = transcription_response.get("text", "")
        print("TRANSCRIPTION: ", transcription)

        messages = get_user_session(user_id)
        messages.append({
            "role": "user",
            "content": transcription,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

        # Limit the number of messages
        messages = limit_messages(messages)

        # Prepend the system prompt
        messages.insert(0, SYSTEM_PROMPT)

        gpt_response = await send_gpt_request(messages)
        gpt_text = gpt_response["choices"][0]["message"]["content"].strip()
        messages.append({
            "role": "assistant",
            "content": gpt_text,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        print("GPT_RESPONSE: ", gpt_text)

        # Remove the system prompt before storing the messages
        if messages and messages[0] == SYSTEM_PROMPT:
            messages.pop(0)

        update_user_session(user_id, messages)

        tts_audio_data = await send_tts_request(gpt_text)

        # Amplify audio
        amplified_audio_data = amplify_audio(tts_audio_data, factor=20)

        # Ensuring the returned audio has the correct sample rate and channels
        final_wav_data = add_wav_header(amplified_audio_data, sample_rate=20000, num_channels=1, bits_per_sample=16)

        return final_wav_data

    except aiohttp.ClientResponseError as e:
        return {
            'statusCode': 500,
            'body': f"Error processing audio: {str(e)}"
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }
