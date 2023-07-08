import os
from fastapi import FastAPI, UploadFile, Form, File, HTTPException
from sound_features import (estimate_pitch_yin, measure_speech_clarity_mfcc, estimate_tonality_hps,
                            measure_energy_rms, detect_silence, detect_voice_gender)
from audio_to_text import transcribe_it
from pydantic import BaseModel, Field
import sqlite3

from audio_to_text import transcribe_it
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

conn = sqlite3.connect('database.db')
cursor = conn.cursor()


# Define CORS origins whitelist
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://example.com",
    "https://example.com",
]

# Add CORS middleware with whitelist
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ClientInfoCreate(BaseModel):
    vertical: str = Field(..., min_length=1)
    self: int = 0
    spouse: int = 0
    children: int = 0
    parent_id: int = 0
    oldest_parent_age: int = None
    oldest_children_age: int = None


class ClientReportCreate(BaseModel):
    client_id: int
    report: str


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
    gender = detect_voice_gender(audioFile.filename)
    # transcript = None

    sc_judger = "Good" if sc >= 0.5 else "Bad"
    st_judger = "Good" if st is not None else "Bad"
    sp_judger = "Good" if sp > 0.2 else "Bad"
    se_judger = "Good" if se >= 0.1 else "Bad"

    os.remove(audioFile.filename)

    return {
        "message": "Audio processed",
        "question": cal,
        "gender": gender,
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


@app.post("/client-info")
async def create_client_info(client_info: ClientInfoCreate):
    query = """
        INSERT INTO client_info (vertical, self, spouse, children, parent_id, oldest_parent_age, oldest_children_age)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    parameters = (
        client_info.vertical,
        client_info.self,
        client_info.spouse,
        client_info.children,
        client_info.parent_id,
        client_info.oldest_parent_age,
        client_info.oldest_children_age,
    )
    try:
        cursor.execute(query, parameters)
        conn.commit()
        client_id = cursor.lastrowid
        return {"client_id": client_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/client-report")
async def create_client_report(client_report: ClientReportCreate):
    query = """
        INSERT INTO client_report (client_id, report)
        VALUES (?, ?)
    """
    parameters = (client_report.client_id, client_report.report)
    try:
        cursor.execute(query, parameters)
        conn.commit()
        return {"message": "Client report created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
