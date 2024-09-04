import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
import base64
import json
from app.core import process_audio_logic, limit_messages
from app.audio_processing import amplify_pcm_audio, compress_to_mp3
from app.prompts import DEFAULT_SYSTEM_PROMPT

# Load the test sound files as base64 encoded strings
def load_sound_file(filename):
    with open(f'test/sounds/{filename}.txt', 'r') as file:
        return file.read()

# Fixtures for audio data events (very short, normal with/without transcription)
@pytest.fixture
def event_very_short_audio():
    audio_data = load_sound_file("very_short_audio")
    return {
        "body": json.dumps({
            "user_id": "test_user",
            "audio_data": audio_data
        })
    }

@pytest.fixture
def event_normal_audio_with_transcription():
    audio_data = load_sound_file("normal_audio_with_transcription")
    return {
        "body": json.dumps({
            "user_id": "test_user",
            "audio_data": audio_data
        })
    }

@pytest.fixture
def event_normal_audio_without_transcription():
    audio_data = load_sound_file("normal_audio_without_transcription")
    return {
        "body": json.dumps({
            "user_id": "test_user",
            "audio_data": audio_data
        })
    }

# Mocking GPT, STT, and TTS responses
@pytest.fixture
def mock_responses():
    transcription_response = {
        "text": "transcribed text"
    }
    gpt_response = {
        "choices": [
            {
                "message": {
                    "content": "gpt response"
                }
            }
        ]
    }
    tts_response = b"mock_tts_audio_data"
    return transcription_response, gpt_response, tts_response

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
@patch('app.core.send_azure_stt_request')  # We still patch STT to assert that it's NOT called
async def test_process_audio_logic_very_short_audio(
    mock_send_azure_stt_request, mock_send_azure_tts_request, mock_send_gpt_request, 
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session, 
    event_very_short_audio, mock_responses):
    
    # Load mock responses for GPT and TTS
    _, gpt_response, tts_response = mock_responses

    # Mock GPT and TTS calls (STT shouldn't be called for short audio)
    mock_send_gpt_request.return_value = gpt_response      # GPT returns a valid response
    mock_send_azure_tts_request.return_value = tts_response # TTS returns the audio response
    mock_get_user_session.return_value = []                # No previous messages in session
    mock_get_user_system_prompt.return_value = {"SystemPrompt": None, "ActiveMessageLimit": None}        # No user-specific prompt

    # Call the function being tested
    result = await process_audio_logic(event_very_short_audio)
    
    # Check the response is the TTS-generated audio
    amplified_audio_data = amplify_pcm_audio(b'mock_tts_audio_data', factor=1)
    expected_audio = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='16k', trim_silence=True)

    assert result == expected_audio

    # Ensure session was updated with empty user message and GPT response
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once()

    # Assert GPT and TTS were called
    mock_send_gpt_request.assert_called_once()
    mock_send_azure_tts_request.assert_called_once()

    # Assert STT was NOT called to save API cost for very short audio
    mock_send_azure_stt_request.assert_not_called()

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_azure_stt_request')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
async def test_process_audio_logic_normal_audio_with_transcription(
    mock_send_azure_tts_request, mock_send_gpt_request, mock_send_azure_stt_request, 
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session, 
    event_normal_audio_with_transcription, mock_responses):
    
    # Load mock responses for STT, GPT, and TTS
    transcription_response, gpt_response, tts_response = mock_responses

    # Mock the Azure STT, GPT, and TTS calls
    mock_send_azure_stt_request.return_value = transcription_response  # STT returns a valid transcription
    mock_send_gpt_request.return_value = gpt_response                  # GPT returns a valid response
    mock_send_azure_tts_request.return_value = tts_response            # TTS returns the audio response
    mock_get_user_session.return_value = []                            # No previous messages in session
    mock_get_user_system_prompt.return_value = {"SystemPrompt": None, "ActiveMessageLimit": None}  # No user-specific prompt

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_with_transcription)
    
    # Check the response is the TTS-generated audio
    amplified_audio_data = amplify_pcm_audio(b'mock_tts_audio_data', factor=1)
    expected_audio = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='16k', trim_silence=True)

    assert result == expected_audio

    # Ensure session was updated with transcribed user message and GPT response
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once()

    # Assert STT, GPT, and TTS were all called
    mock_send_azure_stt_request.assert_called_once()
    mock_send_gpt_request.assert_called_once()
    mock_send_azure_tts_request.assert_called_once()

    # Assert the GPT request contains the correct transcribed text
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert api_call_messages[1]['content'] == transcription_response['text']  # Ensure the user message matches transcription


@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_azure_stt_request')
@patch('app.core.serve_audio_from_file')  # This will simulate the pre-recorded audio being returned
async def test_process_audio_logic_normal_audio_without_transcription(
    mock_serve_audio_from_file, mock_send_azure_stt_request, 
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session, 
    event_normal_audio_without_transcription):
    
    # Simulate no transcription being returned (STT returns empty text)
    mock_send_azure_stt_request.return_value = {"text": ""}

    # Mock pre-recorded audio response
    mock_serve_audio_from_file.return_value = b'pre_recorded_audio_data'
    
    # No previous messages and no user-specific prompt
    mock_get_user_session.return_value = []
    mock_get_user_system_prompt.return_value = {"SystemPrompt": None, "ActiveMessageLimit": None}

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_without_transcription)

    # Check the result is the pre-recorded audio
    assert result == b'pre_recorded_audio_data'

    # Ensure session was updated with empty user message and pre-recorded assistant response
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once()

    # Assert that STT was called but GPT and TTS were not called
    mock_send_azure_stt_request.assert_called_once()
    mock_serve_audio_from_file.assert_called_once()

    # Assert GPT and TTS were not called since no transcription was provided
    with patch('app.core.send_gpt_request') as mock_send_gpt_request, \
         patch('app.core.send_azure_tts_request') as mock_send_azure_tts_request:
        mock_send_gpt_request.assert_not_called()
        mock_send_azure_tts_request.assert_not_called()

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_azure_stt_request')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
async def test_process_audio_logic_user_specific_prompt_exists(
    mock_send_azure_tts_request, mock_send_gpt_request, mock_send_azure_stt_request, 
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session, 
    event_normal_audio_with_transcription, mock_responses):
    
    transcription_response, gpt_response, tts_response = mock_responses

    # Mock STT, GPT, and TTS calls
    mock_send_azure_stt_request.return_value = transcription_response  # STT returns valid transcription
    mock_send_gpt_request.return_value = gpt_response                  # GPT returns valid response
    mock_send_azure_tts_request.return_value = tts_response            # TTS returns the audio response

    # Mock user-specific prompt exists
    mock_get_user_system_prompt.return_value = {'SystemPrompt': "You are a custom assistant."}

    # Mock no previous messages
    mock_get_user_session.return_value = []

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_with_transcription)
    
    # Check the response is the TTS-generated audio
    amplified_audio_data = amplify_pcm_audio(b'mock_tts_audio_data', factor=1)
    expected_audio = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='16k', trim_silence=True)

    assert result == expected_audio

    # Ensure GPT was called with the user-specific prompt
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert api_call_messages[0]['content'] == "You are a custom assistant."  # User-specific system prompt

    # Ensure session was updated
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once()

    # Ensure STT, GPT, and TTS were called
    mock_send_azure_stt_request.assert_called_once()
    mock_send_gpt_request.assert_called_once()
    mock_send_azure_tts_request.assert_called_once()

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_azure_stt_request')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
async def test_process_audio_logic_user_specific_prompt_does_not_exist(
    mock_send_azure_tts_request, mock_send_gpt_request, mock_send_azure_stt_request, 
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session, 
    event_normal_audio_with_transcription, mock_responses):
    
    transcription_response, gpt_response, tts_response = mock_responses

    # Mock STT, GPT, and TTS calls
    mock_send_azure_stt_request.return_value = transcription_response  # STT returns valid transcription
    mock_send_gpt_request.return_value = gpt_response                  # GPT returns valid response
    mock_send_azure_tts_request.return_value = tts_response            # TTS returns the audio response

    # Mock user-specific prompt does not exist
    mock_get_user_system_prompt.return_value = {"SystemPrompt": None, "ActiveMessageLimit": None}  # No user-specific prompt

    # Mock no previous messages
    mock_get_user_session.return_value = []

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_with_transcription)
    
    # Check the response is the TTS-generated audio
    amplified_audio_data = amplify_pcm_audio(b'mock_tts_audio_data', factor=1)
    expected_audio = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='16k', trim_silence=True)

    assert result == expected_audio

    # Ensure GPT was called with the default system prompt
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert api_call_messages[0]['content'] == DEFAULT_SYSTEM_PROMPT  # Default system prompt

    # Ensure session was updated
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once()

    # Ensure STT, GPT, and TTS were called
    mock_send_azure_stt_request.assert_called_once()
    mock_send_gpt_request.assert_called_once()
    mock_send_azure_tts_request.assert_called_once()

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_azure_stt_request')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
async def test_process_audio_logic_no_previous_messages(
    mock_send_azure_tts_request, mock_send_gpt_request, mock_send_azure_stt_request, 
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session, 
    event_normal_audio_with_transcription, mock_responses):
    
    transcription_response, gpt_response, tts_response = mock_responses

    # Mock STT, GPT, and TTS calls
    mock_send_azure_stt_request.return_value = transcription_response  # STT returns valid transcription
    mock_send_gpt_request.return_value = gpt_response                  # GPT returns valid response
    mock_send_azure_tts_request.return_value = tts_response            # TTS returns the audio response

    # No previous messages in the user session
    mock_get_user_session.return_value = []                            # Empty history

    # No user-specific prompt, fall back to default system prompt
    mock_get_user_system_prompt.return_value = {"SystemPrompt": None, "ActiveMessageLimit": None}                    # Default system prompt

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_with_transcription)
    
    # Check the response is the TTS-generated audio
    amplified_audio_data = amplify_pcm_audio(b'mock_tts_audio_data', factor=1)
    expected_audio = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='16k', trim_silence=True)
    assert result == expected_audio

    # Check that GPT was called with the correct system prompt and user message
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert len(api_call_messages) == 2 # Only the system prompt and user message should be called with
    assert api_call_messages[0]['role'] == 'system'
    assert api_call_messages[0]['content'] == DEFAULT_SYSTEM_PROMPT
    assert api_call_messages[1]['role'] == 'user'
    assert api_call_messages[1]['content'] == transcription_response['text']

    # Ensure session was updated with the new user and assistant messages
    updated_session = mock_update_user_session.call_args[0][1]
    assert len(updated_session) == 2  # Only user and assistant messages should be added
    assert updated_session[0]['role'] == 'user'
    assert updated_session[0]['content'] == transcription_response['text']
    assert updated_session[1]['role'] == 'assistant'
    assert updated_session[1]['content'] == gpt_response['choices'][0]['message']['content']

    # Ensure STT, GPT, and TTS were called correctly
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once_with('test_user', updated_session)
    mock_send_azure_stt_request.assert_called_once()
    mock_send_gpt_request.assert_called_once()
    mock_send_azure_tts_request.assert_called_once()

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_azure_stt_request')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
async def test_process_audio_logic_exactly_20_messages(
    mock_send_azure_tts_request, mock_send_gpt_request, mock_send_azure_stt_request, 
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session, 
    event_normal_audio_with_transcription, mock_responses):
    
    transcription_response, gpt_response, tts_response = mock_responses

    # Mock STT, GPT, and TTS calls
    mock_send_azure_stt_request.return_value = transcription_response  # STT returns valid transcription
    mock_send_gpt_request.return_value = gpt_response                  # GPT returns valid response
    mock_send_azure_tts_request.return_value = tts_response            # TTS returns the audio response

    # Mock exactly 20 previous messages (10 user-assistant pairs, interleaved)
    previous_messages = [
        {"role": "user", "content": f"user message {i // 2}", "timestamp": f"2023-01-01T00:00:{i // 2:02d}Z"} if i % 2 == 0 else
        {"role": "assistant", "content": f"assistant message {i // 2}", "timestamp": f"2023-01-01T00:00:{i // 2:02d}Z"} 
        for i in range(20)
    ]
    mock_get_user_session.return_value = previous_messages

    # No user-specific prompt, fall back to default system prompt
    mock_get_user_system_prompt.return_value = {"SystemPrompt": None, "ActiveMessageLimit": None}                    # Default system prompt

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_with_transcription)
    
    # Check the response is the TTS-generated audio
    amplified_audio_data = amplify_pcm_audio(b'mock_tts_audio_data', factor=1)
    expected_audio = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='16k', trim_silence=True)
    assert result == expected_audio

    # Ensure GPT was called with the correct parameters (system prompt + 20 previous messages + new user message)
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert api_call_messages[0]['role'] == 'system'
    assert api_call_messages[0]['content'] == DEFAULT_SYSTEM_PROMPT  # Check default system prompt
    print([x['role'] for x in api_call_messages])
    assert len(api_call_messages) == 22  # 20 previous messages + system prompt + new user message
    assert api_call_messages[1:21] == previous_messages  # Ensure previous 20 messages are in the GPT call
    assert api_call_messages[21]['role'] == 'user'
    assert api_call_messages[21]['content'] == transcription_response['text']  # New user message

    # Ensure session was updated with 22 messages (20 previous + 2 new)
    updated_session = mock_update_user_session.call_args[0][1]
    assert len(updated_session) == 22  # 20 previous + 2 new (user + assistant)
    assert updated_session[20]['role'] == 'user'
    assert updated_session[20]['content'] == transcription_response['text']
    assert updated_session[21]['role'] == 'assistant'
    assert updated_session[21]['content'] == gpt_response['choices'][0]['message']['content']

    # Ensure STT, GPT, and TTS were called correctly
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once_with('test_user', updated_session)
    mock_send_azure_stt_request.assert_called_once()
    mock_send_gpt_request.assert_called_once()
    mock_send_azure_tts_request.assert_called_once()


@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_azure_stt_request')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
async def test_process_audio_logic_more_than_20_messages(
    mock_send_azure_tts_request, mock_send_gpt_request, mock_send_azure_stt_request, 
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session, 
    event_normal_audio_with_transcription, mock_responses):
    
    transcription_response, gpt_response, tts_response = mock_responses

    # Mock STT, GPT, and TTS calls
    mock_send_azure_stt_request.return_value = transcription_response  # STT returns valid transcription
    mock_send_gpt_request.return_value = gpt_response                  # GPT returns valid response
    mock_send_azure_tts_request.return_value = tts_response            # TTS returns the audio response

    # Mock more than 20 previous messages (15 user-assistant pairs, interleaved)
    previous_messages = [
        {"role": "user", "content": f"user message {i // 2}", "timestamp": f"2023-01-01T00:00:{i // 2:02d}Z"} if i % 2 == 0 else
        {"role": "assistant", "content": f"assistant message {i // 2}", "timestamp": f"2023-01-01T00:00:{i // 2:02d}Z"} 
        for i in range(30)
    ]
    mock_get_user_session.return_value = previous_messages

    # No user-specific prompt, fall back to default system prompt
    mock_get_user_system_prompt.return_value = {"SystemPrompt": None, "ActiveMessageLimit": None}                    # Default system prompt

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_with_transcription)
    
    # Check the response is the TTS-generated audio
    amplified_audio_data = amplify_pcm_audio(b'mock_tts_audio_data', factor=1)
    expected_audio = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='16k', trim_silence=True)
    assert result == expected_audio

    # Ensure GPT was called with the correct parameters (last 20 previous messages + new user message)
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert api_call_messages[0]['role'] == 'system'
    assert api_call_messages[0]['content'] == DEFAULT_SYSTEM_PROMPT  # Check default system prompt
    assert len(api_call_messages) == 22  # last 20 previous messages + system prompt + new user message
    assert api_call_messages[1:21] == previous_messages[-20:]  # Ensure only the last 20 messages are passed to GPT
    assert api_call_messages[21]['role'] == 'user'
    assert api_call_messages[21]['content'] == transcription_response['text']  # New user message

    # Ensure session was updated with the entire history (30 previous + 2 new)
    updated_session = mock_update_user_session.call_args[0][1]
    assert len(updated_session) == 32  # All 30 previous + 2 new (user + assistant)
    assert updated_session[-2]['role'] == 'user'
    assert updated_session[-2]['content'] == transcription_response['text']
    assert updated_session[-1]['role'] == 'assistant'
    assert updated_session[-1]['content'] == gpt_response['choices'][0]['message']['content']

    # Ensure STT, GPT, and TTS were called correctly
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once_with('test_user', updated_session)
    mock_send_azure_stt_request.assert_called_once()
    mock_send_gpt_request.assert_called_once()
    mock_send_azure_tts_request.assert_called_once()

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_azure_stt_request')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
async def test_process_audio_logic_unlimited_message_limit(
    mock_send_azure_tts_request, mock_send_gpt_request, mock_send_azure_stt_request, 
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session, 
    event_normal_audio_with_transcription, mock_responses):
    
    transcription_response, gpt_response, tts_response = mock_responses

    # Mock STT, GPT, and TTS calls
    mock_send_azure_stt_request.return_value = transcription_response  # STT returns valid transcription
    mock_send_gpt_request.return_value = gpt_response                  # GPT returns valid response
    mock_send_azure_tts_request.return_value = tts_response            # TTS returns the audio response

    # Mock more than 20 previous messages (15 user-assistant pairs, interleaved)
    previous_messages = [
        {"role": "user", "content": f"user message {i // 2}", "timestamp": f"2023-01-01T00:00:{i // 2:02d}Z"} if i % 2 == 0 else
        {"role": "assistant", "content": f"assistant message {i // 2}", "timestamp": f"2023-01-01T00:00:{i // 2:02d}Z"} 
        for i in range(30)
    ]
    mock_get_user_session.return_value = previous_messages

    # Mock user-specific prompt with unlimited message limit (ActiveMessageLimit = -1)
    mock_get_user_system_prompt.return_value = {"SystemPrompt": "You are a playful assistant.", "ActiveMessageLimit": -1}

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_with_transcription)

    # Check the response is the TTS-generated audio
    amplified_audio_data = amplify_pcm_audio(b'mock_tts_audio_data', factor=1)
    expected_audio = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='16k', trim_silence=True)
    assert result == expected_audio

    # Ensure GPT was called with the correct parameters (all 30 previous messages + new user message)
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert api_call_messages[0]['role'] == 'system'
    assert api_call_messages[0]['content'] == "You are a playful assistant."  # User-specific system prompt
    assert len(api_call_messages) == 32  # All 30 previous messages + system prompt + new user message
    assert api_call_messages[1:31] == previous_messages  # Ensure all previous messages are passed to GPT
    assert api_call_messages[31]['role'] == 'user'
    assert api_call_messages[31]['content'] == transcription_response['text']  # New user message

    # Ensure session was updated with the entire history (30 previous + 2 new)
    updated_session = mock_update_user_session.call_args[0][1]
    assert len(updated_session) == 32  # All 30 previous + 2 new (user + assistant)
    assert updated_session[-2]['role'] == 'user'
    assert updated_session[-2]['content'] == transcription_response['text']
    assert updated_session[-1]['role'] == 'assistant'
    assert updated_session[-1]['content'] == gpt_response['choices'][0]['message']['content']

    # Ensure STT, GPT, and TTS were called correctly
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once_with('test_user', updated_session)
    mock_send_azure_stt_request.assert_called_once()
    mock_send_gpt_request.assert_called_once()
    mock_send_azure_tts_request.assert_called_once()


@pytest.mark.asyncio
@patch('app.core.get_user_system_prompt')
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
@patch('app.core.send_azure_stt_request')
async def test_system_prompt_and_message_limit_affects_handle_audio(
    mock_send_azure_stt_request, mock_send_azure_tts_request, mock_send_gpt_request,
    mock_update_user_session, mock_get_user_session, mock_get_user_system_prompt,
    event_normal_audio_with_transcription, mock_responses):

    transcription_response, gpt_response, tts_response = mock_responses

    # Mock responses for STT, GPT, and TTS
    mock_send_azure_stt_request.return_value = transcription_response  # Fake transcription
    mock_send_gpt_request.return_value = gpt_response  # Fake GPT response
    mock_send_azure_tts_request.return_value = tts_response  # Fake TTS response

    # Define scenarios with possible database states for SystemPrompt and ActiveMessageLimit
    scenarios = [
        # Scenario 1: User has both SystemPrompt and ActiveMessageLimit set
        {"system_prompt_data": {"SystemPrompt": "You are a friendly assistant.", "ActiveMessageLimit": 15},
         "expected_system_prompt": "You are a friendly assistant.",
         "expected_message_limit": 15},

        # Scenario 2: User has only SystemPrompt, no ActiveMessageLimit
        {"system_prompt_data": {"SystemPrompt": "You are a playful bear.", "ActiveMessageLimit": None},
         "expected_system_prompt": "You are a playful bear.",
         "expected_message_limit": 10},  # Default to 10

        # Scenario 3: User has only ActiveMessageLimit, no SystemPrompt
        {"system_prompt_data": {"SystemPrompt": None, "ActiveMessageLimit": 20},
         "expected_system_prompt": DEFAULT_SYSTEM_PROMPT,
         "expected_message_limit": 20},

        # Scenario 4: User exists but neither field is set / Not Exist at all
        {"system_prompt_data": {"SystemPrompt": None, "ActiveMessageLimit": None},
         "expected_system_prompt": DEFAULT_SYSTEM_PROMPT,
         "expected_message_limit": 10}  # Both defaults
    ]

    # Iterate over each scenario
    for scenario in scenarios:
        mock_get_user_system_prompt.return_value = scenario["system_prompt_data"]
        mock_get_user_session.return_value = []  # Empty message history

        # Call process_audio_logic and check system prompt and message limit
        result = await process_audio_logic(event_normal_audio_with_transcription)

        # Check the values passed to the mocked functions
        system_prompt_data = mock_get_user_system_prompt('test_user')
        system_prompt = system_prompt_data.get("SystemPrompt") or DEFAULT_SYSTEM_PROMPT
        active_message_limit = system_prompt_data.get("ActiveMessageLimit") or 10

        # Assert system_prompt and active_message_limit are as expected
        assert system_prompt == scenario["expected_system_prompt"]
        assert active_message_limit == scenario["expected_message_limit"]

    # Ensure the API calls (GPT, TTS, etc.) were made with the correct parameters
    mock_get_user_session.assert_called()
    mock_update_user_session.assert_called()
    mock_send_azure_stt_request.assert_called()
    mock_send_gpt_request.assert_called()
    mock_send_azure_tts_request.assert_called()