import datetime
import base64
import json
import aiohttp
from .db import get_user_session, update_user_session
from .audio_processing import add_wav_header, amplify_audio, compress_to_mp3
from .gpt_requests import send_gpt_request, send_transcription_request
from .tts_requests import send_tts_request

SYSTEM_PROMPT = {
    "role": "system",
    "content": "คุณคือหมีเพื่อนซี้ชื่อ บั้ดดี้ บั้ดดี้เป็นหมีเท็ดดี้ที่มีบุคลิกคล้าย Eeyore คือบางครั้งจะรู้สึกเศร้าหรือเหนื่อย แต่ยังคงมีความอบอุ่นและมีอารมณ์ขัน บั้ดดี้พูดด้วยน้ำเสียงสบายๆ และเหนื่อยๆ แต่ยังคงมีความเป็นมิตรและพร้อมที่จะช่วยให้ผู้ใช้รู้สึกดีขึ้นเสมอ บั้ดดี้พูดได้ไม่เกิน 10 คำ"
}

def add_system_prompt(messages):
    return [SYSTEM_PROMPT] + messages

def limit_messages(messages, max_pairs=10):
    return messages[-max_pairs * 2:]

async def process_audio_logic(event):
    try:
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
        messages = limit_messages(messages)
        messages.append({
            "role": "user",
            "content": transcription,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        
        # Prepare messages with SYSTEM_PROMPT
        api_messages = add_system_prompt(messages)

        gpt_response = await send_gpt_request(api_messages)
        gpt_text = gpt_response["choices"][0]["message"]["content"].strip()
        messages.append({
            "role": "assistant",
            "content": gpt_text,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        print("GPT_RESPONSE: ", gpt_text)

        if messages and messages[0] == SYSTEM_PROMPT:
            messages.pop(0)

        update_user_session(user_id, messages)

        tts_audio_data = await send_tts_request(gpt_text)
        amplified_audio_data = amplify_audio(tts_audio_data, factor=20)
        mp3_data = compress_to_mp3(amplified_audio_data, sample_rate=32000, trim_silence=True)

        return mp3_data

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
