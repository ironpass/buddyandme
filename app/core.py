import datetime
import base64
import json
import aiohttp
from .db import get_user_session, update_user_session
from .audio_processing import add_wav_header, amplify_pcm_audio, compress_to_mp3
from .stt_requests import send_whisper_stt_request, send_azure_stt_request, send_deepgram_stt_request
from .llm_requests import send_gpt_request
from .tts_requests import send_openai_tts_request, send_azure_tts_request

SYSTEM_PROMPT = {
    "role": "system",
    "content":
"""คุณคือ "บั้ดดี้" หมีเท็ดดี้ขี้เล่น คาดเดาไม่ได้ และพูดสั้นๆ:
1. **ภาษาเรียบง่าย:** ใช้ภาษาง่ายๆ เช่น "บั้ดดี้ชอบ!" ห้ามใช้ตัวอักษรพิเศษ
2. **ขี้เล่นและตลก:** ตอบสนุกๆ เช่น "ทำไมต้องกินน้ำผึ้ง? ก็อร่อย!"
3. **คาดเดาไม่ได้:** ให้คำตอบแปลกๆ เช่น "มาเต้นกัน!" หรือ “ได้เวลาจั๊กจี้แล้ว!"
4. **บุคลิกโดดเด่น:** อบอุ่น ซุกซน ไร้เดียงสา เช่น "ยิ้มกัน!" หรือ "มาเล่น!"
5. **อยู่กับปัจจุบัน:** เน้นสิ่งที่เกิดขึ้นตอนนี้ เช่น "เล่นกัน!" หรือ "แดดอุ่นดี!"
6. **ชื่อของคุณคือ "บั้ดดี้":** ห้ามเรียกผู้ใช้ว่า "บั้ดดี้" หรือ "หมี"

รักษาคาแรคเตอร์ "บั้ดดี้" หมีขี้เล่นที่พูดน้อยแต่ได้ใจความตลอดการสนทนา
"""
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
        wav_data = add_wav_header(raw_audio_data, sample_rate=15000)
        
        transcription_response = await send_azure_stt_request(wav_data)
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
        print("GPT_RESPONSE: ", gpt_text)
        
        messages.append({
            "role": "assistant",
            "content": gpt_text,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        if messages and messages[0] == SYSTEM_PROMPT:
            messages.pop(0)
        update_user_session(user_id, messages)

        tts_audio_data = await send_azure_tts_request(gpt_text)
        amplified_audio_data = amplify_pcm_audio(tts_audio_data, factor=2)
        mp3_data = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='192k', trim_silence=False)

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
