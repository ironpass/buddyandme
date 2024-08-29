import datetime
import base64
import json
import aiohttp
from .db import get_user_session, update_user_session, get_user_system_prompt
from .audio_processing import add_wav_header, amplify_pcm_audio, compress_to_mp3
from .stt_requests import send_whisper_stt_request, send_azure_stt_request, send_deepgram_stt_request
from .llm_requests import send_gpt_request
from .tts_requests import send_openai_tts_request, send_azure_tts_request
from .constants import DEFAULT_SYSTEM_PROMPT


def add_system_prompt(user_id, messages):
    system_prompt = {
        "role": "system",
        "content": DEFAULT_SYSTEM_PROMPT,
    }

    # Fetch the user-specific system prompt from the database
    user_prompt = get_user_system_prompt(user_id)
    if user_prompt:
        system_prompt["content"] = user_prompt
    
    return [system_prompt] + messages

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
        
        # Prepare messages with user-specific or default SYSTEM_PROMPT
        api_messages = add_system_prompt(user_id, messages)

        gpt_response = await send_gpt_request(api_messages)
        gpt_text = gpt_response["choices"][0]["message"]["content"].strip()
        print("GPT_RESPONSE: ", gpt_text)
        
        messages.append({
            "role": "assistant",
            "content": gpt_text,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        
        # Remove the system prompt from the messages if it exists
        if messages and messages[0]['role'] == 'system':
            messages.pop(0)
        
        update_user_session(user_id, messages)

        tts_audio_data = await send_azure_tts_request(gpt_text)
        amplified_audio_data = amplify_pcm_audio(tts_audio_data, factor=3)
        mp3_data = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='16k', trim_silence=True)

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
