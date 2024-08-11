from pydub import AudioSegment
import io

def get_sample_mp3():
    # Load an MP3 file
    audio = AudioSegment.from_file("app/test/example_sentence.mp3")
    audio = audio.set_channels(1)
    audio = audio.set_frame_rate(32000)
    mp3_io = io.BytesIO()
    audio.export(mp3_io, format="mp3", bitrate='16k')
    mp3_data = mp3_io.getvalue()
    return mp3_data