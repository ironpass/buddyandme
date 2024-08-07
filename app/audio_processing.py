import io
import wave
from pydub import AudioSegment
import io

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

def amplify_audio(pcm_data, factor=2):
    audio = bytearray(pcm_data)
    for i in range(0, len(audio), 2):
        sample = int.from_bytes(audio[i:i+2], byteorder='little', signed=True)
        sample = int(sample * factor)
        sample = max(min(sample, 32767), -32768)
        audio[i:i+2] = sample.to_bytes(2, byteorder='little', signed=True)
    return bytes(audio)

def compress_to_mp3(pcm_data, sample_rate=44100, num_channels=1, bitrate='16k', trim_silence=False):
    """
    Compresses PCM data to MP3 format with reduced size and optional silence trimming.

    :param pcm_data: The raw PCM audio data.
    :param sample_rate: The sample rate of the audio.
    :param num_channels: Number of audio channels (1 for mono, 2 for stereo).
    :param bitrate: Bitrate for MP3 compression.
    :param trim_silence: Whether to trim silence from the beginning and end of the audio.
    :return: Compressed MP3 audio data.
    """
    audio = AudioSegment(
        data=pcm_data,
        sample_width=2,  # Assuming 16-bit PCM
        frame_rate=sample_rate,
        channels=num_channels
    )
    
    # Trim silence if enabled
    if trim_silence:
        audio = audio.strip_silence(silence_len=1000, silence_thresh=-50)

    mp3_io = io.BytesIO()

    audio.export(mp3_io, format="mp3", bitrate=bitrate)

    mp3_data = mp3_io.getvalue()
    
    return mp3_data