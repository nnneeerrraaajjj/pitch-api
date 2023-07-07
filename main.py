from fastapi import FastAPI, UploadFile, Form, File
import librosa

app = FastAPI()


@app.get("/")
def read_root():
    return {"report": "Bad pitch.. Please dont sell insurance"}


@app.post("/process_audio")
async def process_audio(audioFile: UploadFile = File(...), cal: str = Form(...)):
    audio_contents = await audioFile.read()
    with open(audioFile.filename, "wb") as f:
        f.write(audio_contents)

    audio, sr = librosa.load(audioFile.filename)

    sf = librosa.feature.spectral_flatness(y=audio)

    # Return a JSON response
    return {"message": "Audio processed", "cal": cal, "spectral_flatness": sf.tolist()}
