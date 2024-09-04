import datetime
import base64
import json
import aiohttp
import aiofiles
import os
from .db import get_user_session, update_user_session, get_user_system_prompt
from .audio_processing import calculate_audio_length, add_wav_header, amplify_pcm_audio, compress_to_mp3
from .stt_requests import send_azure_stt_request
from .llm_requests import send_gpt_request
from .tts_requests import send_azure_tts_request
from .prompts import DEFAULT_SYSTEM_PROMPT

def extract_body(event):
    """Extract and validate the body from the event."""
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        return body
    except json.JSONDecodeError:
        return {}

def response_error(status_code, message):
    """Return standardized error response."""
    return {
        'statusCode': status_code,
        'body': message
    }

async def process_audio_logic(event):
    try:
        body = extract_body(event)
        if 'audio_data' not in body:
            return response_error(400, 'No audio data found in the request.')
        
        raw_audio_data = base64.b64decode(body['audio_data'])
        user_id = body.get('user_id', 'default_user')

        # Fetch full conversation history and system prompt details
        full_messages = get_user_session(user_id)
        system_prompt_data = get_user_system_prompt(user_id)
        system_prompt = system_prompt_data.get("SystemPrompt") or DEFAULT_SYSTEM_PROMPT
        active_message_limit = system_prompt_data.get("ActiveMessageLimit") or 10

        # Determine the audio length
        audio_length_seconds = calculate_audio_length(raw_audio_data, sample_rate=15000)

        # Handle short or normal audio
        if audio_length_seconds < 0.4:
            full_updated_messages, response = await handle_short_audio(user_id, full_messages, active_message_limit, system_prompt)
        else:
            full_updated_messages, response = await handle_audio(user_id, raw_audio_data, full_messages, active_message_limit, system_prompt)

        # Update session only once with full message history
        update_user_session(user_id, full_updated_messages)

        return response

    except aiohttp.ClientResponseError as e:
        return response_error(500, f"Error processing audio: {str(e)}")
    except Exception as e:
        return response_error(500, f"Error: {str(e)}")


async def handle_short_audio(user_id, full_messages, active_message_limit, system_prompt):
    """Handle very short audio by generating a GPT response."""
    limited_messages = limit_messages(full_messages, active_message_limit)

    gpt_response = await generate_gpt_response(system_prompt, append_message(limited_messages, "", "user"))

    full_messages = append_message(full_messages, "", "user")
    full_messages = append_message(full_messages, gpt_response, "assistant")

    return full_messages, await convert_text_to_audio_and_respond(gpt_response)

async def handle_audio(user_id, raw_audio_data, full_messages, active_message_limit, system_prompt):
    """Handle normal-length audio with or without transcription."""
    transcription = await transcribe_audio(raw_audio_data)

    if not transcription:
        return await handle_no_transcription(user_id, full_messages)

    return await handle_transcription(user_id, transcription, full_messages, active_message_limit, system_prompt)


async def handle_no_transcription(user_id, full_messages):
    """Handle the case where no transcription is available."""
    full_messages = append_message(full_messages, "", "user")
    full_messages = append_message(full_messages, "อะไรนะ บั้ดดี้ขออีกที", "assistant")

    return full_messages, await serve_audio_from_file("say_again.mp3")


async def handle_transcription(user_id, transcription, full_messages, active_message_limit, system_prompt):
    """Handle valid transcription."""
    limited_messages = limit_messages(full_messages, active_message_limit)
    gpt_response = await generate_gpt_response(system_prompt, append_message(limited_messages, transcription, "user"))

    full_messages = append_message(full_messages, transcription, "user")
    full_messages = append_message(full_messages, gpt_response, "assistant")

    return full_messages, await convert_text_to_audio_and_respond(gpt_response)


def append_message(messages, content, role, timestamp=None):
    """Append a message with the specified role and optional timestamp."""
    if not timestamp:
        timestamp = datetime.datetime.utcnow().isoformat()

    print("Role:", role, ":", content)
    return messages + [{
        "role": role,
        "content": content,
        "timestamp": timestamp
    }]

def limit_messages(messages, active_message_limit):
    """Limit the number of message pairs for GPT API calls."""
    if active_message_limit == -1:  # Handle unlimited case
        return messages

    # Calculate the correct slice index
    limit_slice_index = int(-active_message_limit * 2)
    return messages[limit_slice_index:]

async def generate_gpt_response(system_prompt, api_messages):
    """Generate a GPT response based on the system prompt and provided conversation history."""
    # Include the system prompt and call GPT API
    api_messages = [{"role": "system", "content": system_prompt}] + api_messages
    print("len of api messages: ", api_messages)
    gpt_response = await send_gpt_request(api_messages)
    return gpt_response["choices"][0]["message"]["content"].strip()

async def transcribe_audio(raw_audio_data):
    """Send audio to STT service and return transcription."""
    wav_data = add_wav_header(raw_audio_data, sample_rate=15000)
    transcription_response = await send_azure_stt_request(wav_data)
    return transcription_response.get("text", "").strip()

async def serve_audio_from_file(file_name):
    """Serve a pre-recorded MP3 file asynchronously."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    mp3_file_path = os.path.join(base_dir, "sounds", file_name)
    async with aiofiles.open(mp3_file_path, "rb") as mp3_file:
        return await mp3_file.read()

async def convert_text_to_audio_and_respond(assistant_response):
    """Convert the GPT response to audio."""
    tts_audio_data = await send_azure_tts_request(assistant_response)
    tts_audio_data = amplify_pcm_audio(tts_audio_data, factor=1)
    return compress_to_mp3(tts_audio_data, sample_rate=24000, bitrate='16k', trim_silence=True)
