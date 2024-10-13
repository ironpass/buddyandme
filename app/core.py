from dataclasses import dataclass
import time  # Add time module for logging timestamps
from datetime import datetime, timedelta, timezone
import base64
import json
import aiohttp
import aiofiles
import os
from .db import get_user_session, update_user_session, get_user_system_prompt
from .audio_processing import calculate_audio_length, add_wav_header, amplify_pcm_audio, compress_to_mp3
from .stt_requests import send_azure_stt_request
from .llm_requests import send_gpt_request, send_groq_request
from .tts_requests import send_azure_tts_request
from .prompts import DEFAULT_SYSTEM_PROMPT

def log_time(message, start_time):
    """Helper function to log elapsed time with a message."""
    elapsed_time = time.time() - start_time
    print(f"{message}: {elapsed_time:.3f} seconds")

@dataclass
class Response:
    status_code: int
    body: str

async def process_audio_logic(event) -> Response:
    start_time = time.time()

    try:
        # Log extraction time
        body_extraction_start = time.time()
        body = extract_body(event)
        log_time("Body extraction", body_extraction_start)

        if 'audio_data' not in body:
            return Response(
                status_code=400,
                body='No audio data found in the request.'
            )

        audio_decode_start = time.time()
        raw_audio_data = base64.b64decode(body['audio_data'])
        log_time("Audio decode", audio_decode_start)

        user_id = body.get('user_id', 'default_user')

        # Log session retrieval
        session_retrieval_start = time.time()
        full_messages = get_user_session(user_id)
        log_time("User session retrieval", session_retrieval_start)

        # Log system prompt retrieval
        prompt_retrieval_start = time.time()
        system_prompt_data = get_user_system_prompt(user_id)
        system_prompt = system_prompt_data.get("SystemPrompt") or DEFAULT_SYSTEM_PROMPT
        active_message_limit = system_prompt_data.get("ActiveMessageLimit") or 10
        daily_rate_limit = system_prompt_data.get("DailyRateLimit") or 100
        log_time("System prompt retrieval", prompt_retrieval_start)

        if(is_rate_limit_reached(full_messages, daily_rate_limit)):
            return Response(
                status_code=429,
                body='Rate limit reached.'
            )

        # Log audio length calculation
        audio_length_start = time.time()
        audio_length_seconds = calculate_audio_length(raw_audio_data, sample_rate=15000)
        log_time("Audio length calculation", audio_length_start)

        # Handle short or normal audio
        if audio_length_seconds < 0.4:
            handling_audio_start = time.time()
            full_updated_messages, audio_content = await handle_short_audio(user_id, full_messages, active_message_limit, system_prompt)
            log_time("Short audio handling", handling_audio_start)
        else:
            handling_audio_start = time.time()
            full_updated_messages, audio_content = await handle_audio(user_id, raw_audio_data, full_messages, active_message_limit, system_prompt)
            log_time("Normal audio handling", handling_audio_start)

        # Log session update
        session_update_start = time.time()
        update_user_session(user_id, full_updated_messages)
        log_time("User session update", session_update_start)
        log_time("Total process_audio_logic time", start_time)
        
        return Response(
            status_code=200,
            body=audio_content
        )
    except aiohttp.ClientResponseError as e:
        return Response(
            status_code=500,
            body=f"Error processing audio: {str(e)}"
        )
    except Exception as e:
        return Response(
            status_code=500,
            body=f"Error: {str(e)}"
        )

def extract_body(event):
    """Extract and validate the body from the event."""
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        return body
    except json.JSONDecodeError:
        return {}


async def handle_short_audio(user_id, full_messages, active_message_limit, system_prompt):
    """Handle very short audio by generating a GPT response."""
    handle_short_audio_start = time.time()
    limited_messages = limit_messages(full_messages, active_message_limit)

    gpt_start = time.time()
    gpt_response = await generate_gpt_response(system_prompt, append_message(limited_messages, "", "user", verbose=False))
    log_time("GPT response for short audio", gpt_start)

    full_messages = append_message(full_messages, "", "user")
    full_messages = append_message(full_messages, gpt_response, "assistant")

    audio_conversion_start = time.time()
    audio_response = await convert_text_to_audio_and_respond(gpt_response)
    log_time("Audio conversion for short audio", audio_conversion_start)

    log_time("Total short audio handling", handle_short_audio_start)
    return full_messages, audio_response

async def handle_audio(user_id, raw_audio_data, full_messages, active_message_limit, system_prompt):
    """Handle normal-length audio with or without transcription."""
    handle_audio_start = time.time()

    stt_start = time.time()
    transcription = await transcribe_audio(raw_audio_data)
    log_time("STT transcription", stt_start)

    if not transcription:
        return await handle_no_transcription(user_id, full_messages)

    handle_transcription_start = time.time()
    full_messages, response = await handle_transcription(user_id, transcription, full_messages, active_message_limit, system_prompt)
    log_time("Transcription handling", handle_transcription_start)

    log_time("Total audio handling", handle_audio_start)
    return full_messages, response


async def handle_no_transcription(user_id, full_messages):
    """Handle the case where no transcription is available."""
    full_messages = append_message(full_messages, "", "user")
    full_messages = append_message(full_messages, "อะไรนะ บั้ดดี้ขออีกที", "assistant")

    audio_serve_start = time.time()
    audio_response = await serve_audio_from_file("say_again.mp3")
    log_time("Audio serve for no transcription", audio_serve_start)

    return full_messages, audio_response


async def handle_transcription(user_id, transcription, full_messages, active_message_limit, system_prompt):
    """Handle valid transcription."""
    limited_messages = limit_messages(full_messages, active_message_limit)

    gpt_start = time.time()
    gpt_response = await generate_gpt_response(system_prompt, append_message(limited_messages, transcription, "user", verbose=False))
    log_time("GPT response for transcription", gpt_start)

    full_messages = append_message(full_messages, transcription, "user")
    full_messages = append_message(full_messages, gpt_response, "assistant")

    audio_response = await convert_text_to_audio_and_respond(gpt_response)
    return full_messages, audio_response


def append_message(messages, content, role, verbose=True, timestamp=None):
    """Append a message with the specified role and optional timestamp."""
    if timestamp is None:
        timestamp = time.time()  # Current time in UNIX timestamp

    if verbose:
        print("Role:", role, ":", content)

    return messages + [{
        "role": role,
        "content": content,
        "timestamp": str(timestamp)
    }]

def limit_messages(messages, active_message_limit):
    """Limit the number of message pairs for GPT API calls."""
    if active_message_limit == -1:  # Handle unlimited case
        return messages

    # Calculate the correct slice index
    limit_slice_index = int(-active_message_limit * 2)
    return messages[limit_slice_index:]

def is_rate_limit_reached(full_messages, daily_rate_limit):
    message_limit = daily_rate_limit * 2 # Since the messages are appended in pairs

    try:
        # GMT+7 timezone
        tz_gmt7 = timezone(timedelta(hours=7))
        now_gmt7 = datetime.now(tz_gmt7)

        # Calculate the start of the current day (midnight) in GMT+7 timezone
        start_of_day = datetime(
            year=now_gmt7.year,
            month=now_gmt7.month,
            day=now_gmt7.day,
            hour=0,
            minute=0,
            second=0,
            tzinfo=tz_gmt7
        )

        # Get the Unix timestamp for the start of the day
        start_of_day_timestamp = start_of_day.timestamp()

        count_today = 0

        # Iterate through the messages in reverse (newest first)
        for message in reversed(full_messages):
            try:
                message_timestamp_str = message.get('timestamp')
                if message_timestamp_str is None:
                    continue  # Skip if timestamp is missing

                message_timestamp = float(message_timestamp_str)

                if message_timestamp >= start_of_day_timestamp:
                    count_today += 1
                    if count_today >= message_limit:
                        return True  # Rate limit reached
                else:
                    # Since messages are sorted from oldest to newest,
                    # once we find a message older than start_of_day, we can stop
                    break
            except (ValueError, TypeError):
                # Skip messages with invalid timestamp formats
                continue

        return count_today >= message_limit

    except Exception as e:
        print(f"An error occurred: {e}")
        return False

async def generate_gpt_response(system_prompt, api_messages):
    """Generate a GPT response based on the system prompt and provided conversation history."""
    # Include the system prompt and call GPT API
    api_messages = [{"role": "system", "content": system_prompt}] + api_messages
    gpt_response = await send_groq_request(api_messages)
    return gpt_response

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
    audio_tts_start = time.time()
    tts_audio_data = await send_azure_tts_request(assistant_response)
    log_time("Audio TTS", audio_tts_start)

    audio_processing_start = time.time()
    tts_audio_data = amplify_pcm_audio(tts_audio_data, factor=12)
    compressed_audio = compress_to_mp3(tts_audio_data, sample_rate=24000, bitrate='32k')
    log_time("Audio Processing", audio_processing_start)
    return compressed_audio
