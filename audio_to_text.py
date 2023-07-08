from deepgram import Deepgram
import asyncio
import math
from constants import IDEAL_PITCH_ANSWER

DEEPGRAM_API_KEY = 'a92f3b47b78c98b73434b0f3a72253890e093d5c'

async def transcribe_it(filename=None):
    # Initializes the Deepgram SDK
    ideal_words_count = 2.5
    deepgram = Deepgram(DEEPGRAM_API_KEY)
    # Open the audio file
    # source = {'url':'https://do5e1cudimqaf.cloudfront.net/null1688806761692_2ce39462-def4-49a8-8229-16c999ff8cb3_2023_07_08_J5hmZ_recording.mp3'}
    # source = {'url': filename}
    with open(filename, 'rb') as audio:
        source = {'buffer': audio, 'mimetype': 'audio/mp3'}
        response = await deepgram.transcription.prerecorded(source, {'punctuate': True, 'interim_results': False,
                                                                     "model": "base", "language": "hi-Latn"})
    data = response
    print("data", data)
    words_count = 0
    for i in data['results']['channels'][0]['alternatives'][0]['transcript']:
        if i == ' ':
            words_count = words_count + 1

    ideal_word_count_given_time = ideal_words_count * math.floor(data['results']['channels'][0]['alternatives'][0]['words'][words_count]['end'])
    return {
        'transcript': data['results']['channels'][0]['alternatives'][0]['transcript'],
        'words_count': words_count + 1,
        'ideal_word_count_in_time_u_spoke': math.floor(ideal_word_count_given_time),
        'total_time_taken': data['results']['channels'][0]['alternatives'][0]['words'][words_count]['end'],
        'ideal_word_count_per_min': 135,
        'your_words_count_per_min': math.floor(((words_count + 1)/data['results']['channels'][0]['alternatives'][0]['words'][words_count]['end'])*60),
        "ideal_answer": IDEAL_PITCH_ANSWER["2"]
    }
    # return data['results']['channels'][0]['alternatives'][0]['transcript']


# data = asyncio.run(transcribe_it('filler.mp3'))
# print("data", data)

