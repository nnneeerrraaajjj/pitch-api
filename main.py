import os
from fastapi import FastAPI, UploadFile, Form, File
from sound_features import (estimate_pitch_yin, measure_speech_clarity_mfcc, estimate_tonality_hps,
                            measure_energy_rms, detect_silence)
from audio_to_text import transcribe_it

from audio_to_text import transcribe_it

app = FastAPI()


@app.get("/")
def read_root():
    return {"report": "Bad pitch.. Please dont sell anything"}


@app.post("/process_audio")
async def process_audio(audioFile: UploadFile = File(...), cal: str = Form(...)):
    audio_contents = await audioFile.read()
    with open(audioFile.filename, "wb") as f:
        f.write(audio_contents)

    sc = measure_speech_clarity_mfcc(audioFile.filename)
    st = estimate_tonality_hps(audioFile.filename)
    sp = estimate_pitch_yin(audioFile.filename)
    se = measure_energy_rms(audioFile.filename)
    ss = detect_silence(audioFile.filename)
    transcript = await transcribe_it(audioFile.filename)

    sc_judger = "Good" if sc >= 0.5 else "Bad"
    st_judger = "Good" if st is not None else "Bad"
    sp_judger = "Good" if sp > 0 else "Bad"
    se_judger = "Good" if se >= 0.1 else "Bad"

    os.remove(audioFile.filename)

    return {
        "message": "Audio processed",
        "question": cal,
        "speech_clarity": {"value": sc, "judger": sc_judger},
        "tonality": {"value": st, "judger": st_judger},
        "speech_pitch": {"value": sp, "judger": sp_judger},
        "speech_energy": {"value": se, "judger": se_judger},
        "speech silence": ss,
        "transcript": transcript
    }

@app.get("/audio_to_text")
async def transcribe_audio_to_text():
    return await transcribe_it('hockey.mp3')
