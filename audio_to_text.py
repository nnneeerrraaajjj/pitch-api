from deepgram import Deepgram
import asyncio, json

DEEPGRAM_API_KEY = 'f82245e4070590f4c79a2b748ba7349857231233'
# PATH_TO_FILE = '/Users/abhi-hash-8/Desktop/Python-hackthon/tt.mp3'

# async def main(filename):


async def transcribe_it(filename):
    # Initializes the Deepgram SDK
    deepgram = Deepgram(DEEPGRAM_API_KEY)
    # Open the audio file
    # with open(PATH_TO_FILE, 'rb') as audio:
    #     # ...or replace mimetype as appropriate
    #     source = {'buffer': audio, 'mimetype': 'audio/mp3'}
    #     response = await deepgram.transcription.prerecorded(source, {'punctuate': True})
    #     print(json.dumps(response, indent=4))
    # source = {'url':'https://do5e1cudimqaf.cloudfront.net/null1683205111993_fc6d7c83-2445-4fdb-ad6d-41e6e28531f2_2022_01_28_xNKtj_recording.mp3'}
    # source = {'url': filename}
    with open(filename, 'rb') as audio:
        # ...or replace mimetype as appropriate
        source = {'buffer': audio, 'mimetype': 'audio/mp3'}
        response = await deepgram.transcription.prerecorded(source, {'punctuate': True, 'interim_results': False,
                                                                     "model": "base", "language": "hi-Latn"})
    data = response
    words_count = 0
    for i in data['results']['channels'][0]['alternatives'][0]['transcript']:
        if i == ' ':
            words_count = words_count + 1
    print(data['results']['channels'][0]['alternatives'][0]['transcript'])
    print("words", words_count + 1)
    print("total time taken", data['results']['channels'][0]['alternatives'][0]['words'][words_count]['end'])

    return data['results']['channels'][0]['alternatives'][0]['transcript']

# asyncio.run(main())
