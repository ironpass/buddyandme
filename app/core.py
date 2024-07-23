import os
import base64
import aiohttp
import json
import io
import wave

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = "https://api.openai.com/v1"

session_id = "1111111"
sessions = {
    session_id: [{"role": "system", "content": "เธอคือเด็กน้อยแสนน่ารักที่ชื่อบัดดี้ เธอไม่มีเพศ ห้ามใช้คำว่าครับหรือค่ะ ห้ามตอบด้วยemoji และตอบได้ไม่เกิน 5 คำ"}]
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
        data.add_field('prompt', 'buddy, บัดดี้')
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
                json={"model": "gpt-4o", "messages": messages, "max_tokens": 150}) as response:
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
        wav_data = add_wav_header(raw_audio_data)
        transcription_response = await send_transcription_request(wav_data)
        transcription = transcription_response.get("text", "")
        print("TRANSCRIPTION: ", transcription)

        messages = sessions[session_id]
        messages.append({"role": "user", "content": transcription})

        gpt_response = await send_gpt_request(messages)
        gpt_text = gpt_response["choices"][0]["message"]["content"].strip()
        messages.append({"role": "assistant", "content": gpt_text})
        print("GPT_RESPONSE: ", gpt_text)

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
