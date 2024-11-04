import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
import base64
import json
from app.core import process_audio_logic, limit_messages, DEFAULT_SYSTEM_PROMPT
from app.audio_processing import amplify_pcm_audio, compress_to_mp3

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
    gpt_response = "gpt response"
    tts_response = b"mock_tts_audio_data"
    return transcription_response, gpt_response, tts_response

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
@patch('app.core.send_azure_stt_request')  # STT should not be called for very short audio
async def test_process_audio_logic_very_short_audio(
    mock_send_azure_stt_request, mock_send_azure_tts_request, mock_send_gpt_request,
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session,
    event_very_short_audio, mock_responses):
    
    # Load mock responses for GPT and TTS
    _, gpt_response, tts_response = mock_responses

    # Mock GPT and TTS responses
    mock_send_gpt_request.return_value = gpt_response
    mock_send_azure_tts_request.return_value = tts_response
    mock_get_user_session.return_value = []
    mock_get_user_system_prompt.return_value = {
        "SystemPrompt": None,
        "ActiveMessageLimit": None,
        "DailyRateLimit": 100,
        "Whitelist": True
    }

    # Call the function being tested
    result = await process_audio_logic(event_very_short_audio)
    
    # Check the response matches the TTS-generated audio
    amplified_audio_data = amplify_pcm_audio(tts_response, factor=3)
    expected_audio = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='32k')

    assert result.body == expected_audio
    assert result.status_code == 200

    # Assert that session update and system prompt retrieval were called
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once()
    mock_send_gpt_request.assert_called_once()
    mock_send_azure_tts_request.assert_called_once()
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
    mock_send_azure_stt_request.return_value = transcription_response
    mock_send_gpt_request.return_value = gpt_response
    mock_send_azure_tts_request.return_value = tts_response
    mock_get_user_session.return_value = []
    mock_get_user_system_prompt.return_value = {
        "SystemPrompt": None,
        "ActiveMessageLimit": 10,
        "DailyRateLimit": 100,
        "Whitelist": True
    }

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_with_transcription)
    
    # Check the response matches the TTS-generated audio
    amplified_audio_data = amplify_pcm_audio(tts_response, factor=3)
    expected_audio = compress_to_mp3(amplified_audio_data, sample_rate=24000, bitrate='32k')

    assert result.body == expected_audio
    assert result.status_code == 200

    # Ensure session was updated and STT, GPT, and TTS were called
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once()
    mock_send_azure_stt_request.assert_called_once()
    mock_send_gpt_request.assert_called_once()
    mock_send_azure_tts_request.assert_called_once()

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_azure_stt_request')
@patch('app.core.serve_audio_from_file')
async def test_process_audio_logic_normal_audio_without_transcription(
    mock_serve_audio_from_file, mock_send_azure_stt_request,
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session,
    event_normal_audio_without_transcription):
    
    # Simulate STT returning no transcription
    mock_send_azure_stt_request.return_value = {"text": ""}
    mock_serve_audio_from_file.return_value = b'pre_recorded_audio_data'
    mock_get_user_session.return_value = []
    mock_get_user_system_prompt.return_value = {
        "SystemPrompt": None,
        "ActiveMessageLimit": 10,
        "DailyRateLimit": 100,
        "Whitelist": True
    }

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_without_transcription)

    # Check the result is the pre-recorded audio response
    assert result.body == b'pre_recorded_audio_data'
    assert result.status_code == 200

    # Ensure session was updated, and correct API calls were made
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once()
    mock_send_azure_stt_request.assert_called_once()
    mock_serve_audio_from_file.assert_called_once()

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.get_user_system_prompt')
@patch('app.core.send_azure_stt_request')
@patch('app.core.send_gpt_request')
@patch('app.core.send_azure_tts_request')
async def test_process_audio_logic_not_whitelisted(
    mock_send_azure_tts_request, mock_send_gpt_request, mock_send_azure_stt_request,
    mock_get_user_system_prompt, mock_update_user_session, mock_get_user_session,
    event_normal_audio_with_transcription):
    
    # Mock user not being whitelisted
    mock_get_user_system_prompt.return_value = {
        "SystemPrompt": None,
        "ActiveMessageLimit": 10,
        "DailyRateLimit": 100,
        "Whitelist": False  # User not whitelisted
    }
    mock_get_user_session.return_value = []

    # Call the function being tested
    result = await process_audio_logic(event_normal_audio_with_transcription)

    # Check the response indicates the user is not whitelisted
    assert result.body == 'Not whitelisted.'
    assert result.status_code == 400

    # Ensure session retrieval was called but no further API calls were made
    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_not_called()
    mock_send_azure_stt_request.assert_not_called()
    mock_send_gpt_request.assert_not_called()
    mock_send_azure_tts_request.assert_not_called()
