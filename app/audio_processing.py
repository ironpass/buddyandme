import io
import wave

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
