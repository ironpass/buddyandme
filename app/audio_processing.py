import io
import wave
import subprocess

def calculate_audio_length(raw_audio_data, sample_rate=16000, num_channels=1, sample_width=2):
    """
    Calculate the length of raw PCM audio data in seconds.

    :param raw_audio_data: The raw PCM audio data (bytes)
    :param sample_rate: The sample rate in Hz (default is 15000 Hz)
    :param num_channels: Number of audio channels (1 for mono, 2 for stereo)
    :param sample_width: Width of each sample in bytes (default is 2 for 16-bit PCM)
    :return: Duration of the audio in seconds
    """
    num_samples = len(raw_audio_data) // (num_channels * sample_width)
    duration_seconds = num_samples / sample_rate
    return duration_seconds

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

def amplify_pcm_audio(pcm_data, factor=3):
    audio = bytearray(pcm_data)
    for i in range(0, len(audio), 2):
        sample = int.from_bytes(audio[i:i+2], byteorder='little', signed=True)
        sample = int(sample * factor)
        sample = max(min(sample, 32767), -32768)
        audio[i:i+2] = sample.to_bytes(2, byteorder='little', signed=True)
    return bytes(audio)


def compress_to_mp3(pcm_data, sample_rate=24000, num_channels=1, bitrate='32k'):
    process = subprocess.Popen([
        'ffmpeg', '-y', '-f', 's16le', '-ar', str(sample_rate), '-ac', str(num_channels), 
        '-i', 'pipe:0', '-b:a', bitrate, '-f', 'mp3', 'pipe:1'
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    
    mp3_data, _ = process.communicate(input=pcm_data)
    return mp3_data