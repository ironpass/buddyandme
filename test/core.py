import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
import datetime
import base64
import json
from app.core import process_audio_logic, limit_messages, SYSTEM_PROMPT
from app.audio_processing import amplify_audio, add_wav_header

@pytest.fixture
def event():
    return {
        "body": json.dumps({
            "user_id": "test_user",
            "audio_data": base64.b64encode(b"test_audio_data").decode("utf-8")
        })
    }

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
@patch('app.core.send_transcription_request')
@patch('app.core.send_gpt_request')
@patch('app.core.send_tts_request')
async def test_process_audio_logic(mock_send_tts_request, mock_send_gpt_request, mock_send_transcription_request, mock_update_user_session, mock_get_user_session, event, mock_responses):
    transcription_response, gpt_response, tts_response = mock_responses

    mock_send_transcription_request.return_value = transcription_response
    mock_send_gpt_request.return_value = gpt_response
    mock_send_tts_request.return_value = tts_response
    mock_get_user_session.return_value = []

    result = await process_audio_logic(event)
    
    amplified_audio_data = amplify_audio(b'mock_tts_audio_data', factor=20)
    expected = add_wav_header(amplified_audio_data, sample_rate=20000, num_channels=1, bits_per_sample=16)
    
    assert result == expected

    mock_get_user_session.assert_called_once_with('test_user')
    mock_update_user_session.assert_called_once()
    mock_send_transcription_request.assert_called_once()
    mock_send_gpt_request.assert_called_once()
    mock_send_tts_request.assert_called_once()

@pytest.mark.asyncio
@patch('app.core.get_user_session')
@patch('app.core.update_user_session')
@patch('app.core.send_transcription_request')
@patch('app.core.send_gpt_request')
@patch('app.core.send_tts_request')
async def test_process_audio_logic_scenario(mock_send_tts_request, mock_send_gpt_request, mock_send_transcription_request, mock_update_user_session, mock_get_user_session, event, mock_responses):
    transcription_response, gpt_response, tts_response = mock_responses

    mock_send_transcription_request.return_value = transcription_response
    mock_send_gpt_request.return_value = gpt_response
    mock_send_tts_request.return_value = tts_response

    # Scenario 1: No previous messages
    mock_get_user_session.return_value = []
    result = await process_audio_logic(event)
    assert len(mock_update_user_session.call_args[0][1]) == 2  # user + assistant
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert len(api_call_messages) == 2  # SYSTEM_PROMPT + user

    # Scenario 2: Less than 20 previous messages
    mock_get_user_session.return_value = [
        {"role": "user", "content": "previous user message", "timestamp": "2023-01-01T00:00:00Z"},
        {"role": "assistant", "content": "previous assistant message", "timestamp": "2023-01-01T00:00:00Z"}
    ]
    result = await process_audio_logic(event)
    assert len(mock_update_user_session.call_args[0][1]) == 4  # 2 previous + user + assistant
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert len(api_call_messages) == 4  # SYSTEM_PROMPT + 2 previous + user

    # Scenario 3: Exactly 20 messages (10 pairs)
    mock_get_user_session.return_value = [
        {"role": "user", "content": f"user message {i}", "timestamp": f"2023-01-01T00:00:{i:02d}Z"} for i in range(10)
    ] + [
        {"role": "assistant", "content": f"assistant message {i}", "timestamp": f"2023-01-01T00:00:{i:02d}Z"} for i in range(10)
    ]
    result = await process_audio_logic(event)
    assert len(mock_update_user_session.call_args[0][1]) == 22  # 20 previous + user + assistant
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert len(api_call_messages) == 22  # SYSTEM_PROMPT + 20 previous + user

    # Scenario 4: More than 20 messages (should pick last 20)
    mock_get_user_session.return_value = [
        {"role": "user", "content": f"user message {i}", "timestamp": f"2023-01-01T00:00:{i:02d}Z"} for i in range(20)
    ] + [
        {"role": "assistant", "content": f"assistant message {i}", "timestamp": f"2023-01-01T00:00:{i:02d}Z"} for i in range(20)
    ]
    result = await process_audio_logic(event)
    assert len(mock_update_user_session.call_args[0][1]) == 22  # last 20 previous + user + assistant
    api_call_messages = mock_send_gpt_request.call_args[0][0]
    assert len(api_call_messages) == 22  # SYSTEM_PROMPT + last 20 previous + user
    assert api_call_messages == [SYSTEM_PROMPT] + mock_get_user_session.return_value[-20:] + [
        {"role": "user", "content": transcription_response['text'], "timestamp": api_call_messages[-1]['timestamp']}
    ]

    mock_get_user_session.assert_called_with('test_user')
    mock_update_user_session.assert_called()
    mock_send_transcription_request.assert_called()
    mock_send_gpt_request.assert_called()
    mock_send_tts_request.assert_called()

def test_limit_messages():
    messages = [
        {"role": "user", "content": "Message 1", "timestamp": "2023-01-01T00:00:00Z"},
        {"role": "assistant", "content": "Message 2", "timestamp": "2023-01-02T00:00:00Z"},
        {"role": "user", "content": "Message 3", "timestamp": "2023-01-03T00:00:00Z"},
        {"role": "assistant", "content": "Message 4", "timestamp": "2023-01-04T00:00:00Z"},
        {"role": "user", "content": "Message 5", "timestamp": "2023-01-05T00:00:00Z"},
        {"role": "assistant", "content": "Message 6", "timestamp": "2023-01-06T00:00:00Z"},
        {"role": "user", "content": "Message 7", "timestamp": "2023-01-07T00:00:00Z"},
        {"role": "assistant", "content": "Message 8", "timestamp": "2023-01-08T00:00:00Z"},
        {"role": "user", "content": "Message 9", "timestamp": "2023-01-09T00:00:00Z"},
        {"role": "assistant", "content": "Message 10", "timestamp": "2023-01-10T00:00:00Z"},
        {"role": "user", "content": "Message 11", "timestamp": "2023-01-11T00:00:00Z"},
        {"role": "assistant", "content": "Message 12", "timestamp": "2023-01-12T00:00:00Z"},
        {"role": "user", "content": "Message 13", "timestamp": "2023-01-13T00:00:00Z"},
        {"role": "assistant", "content": "Message 14", "timestamp": "2023-01-14T00:00:00Z"},
        {"role": "user", "content": "Message 15", "timestamp": "2023-01-15T00:00:00Z"},
        {"role": "assistant", "content": "Message 16", "timestamp": "2023-01-16T00:00:00Z"},
        {"role": "user", "content": "Message 17", "timestamp": "2023-01-17T00:00:00Z"},
        {"role": "assistant", "content": "Message 18", "timestamp": "2023-01-18T00:00:00Z"},
        {"role": "user", "content": "Message 19", "timestamp": "2023-01-19T00:00:00Z"},
        {"role": "assistant", "content": "Message 20", "timestamp": "2023-01-20T00:00:00Z"},
        {"role": "user", "content": "Message 21", "timestamp": "2023-01-21T00:00:00Z"}
    ]
    limited_messages = limit_messages(messages, 10)
    assert len(limited_messages) == 20
    assert limited_messages[0]['content'] == "Message 2"
    assert limited_messages[-1]['content'] == "Message 21"

if __name__ == '__main__':
    pytest.main()
