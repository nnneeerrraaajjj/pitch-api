import os
from fastapi import FastAPI, UploadFile, Form, File, HTTPException, Request, status
from sound_features import (estimate_pitch_yin, measure_speech_clarity_mfcc, estimate_tonality_hps,
                            measure_energy_rms, detect_silence, detect_voice_gender)
from audio_to_text import transcribe_it
from pydantic import BaseModel, Field
import sqlite3
import json

from audio_to_text import transcribe_it
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict
from typing import List
from starlette.responses import RedirectResponse
from constants import CLIENT_QUESTION

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
async def process_audio(audioFile: UploadFile = File(...), cal: str = Form(...), client_id: str = Form(...)):
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

    analysis = {
        "message": "Audio processed",
        "question": CLIENT_QUESTION[cal],
        "gender": gender,
        "speech_clarity": {"value": sc, "judger": sc_judger},
        "tonality": {"value": st, "judger": st_judger},
        "speech_pitch": {"value": sp, "judger": sp_judger},
        "speech_energy": {"value": se, "judger": se_judger},
        "speech silence": ss,
        "transcript": transcript
    }

    feedback = evaluator_func(analysis)

    analysis["feedback"] = feedback
    del analysis["transcript"]

    payload = {
        "client_id": client_id,
        "report": json.dumps(analysis)
    }

    res = await create_client_report(payload)
    if cal == '4':
        collated_report = create_collated_report(client_id)
        print("cool",collated_report)
        comprehensive_report = generate_summary_report(collated_report['averages'], collated_report['combined_feedback'])
        print(comprehensive_report)
        final_result = {
            "summary": comprehensive_report,
            "voice_analysis": collated_report['averages']
        }
        payload = {
            "client_id": client_id,
            "report": json.dumps(final_result)
        }
        res = await create_client_report(payload)

        return RedirectResponse(url=f'/report/{client_id}', status_code=301)

    return res


@app.get("/final-report/{client_id}")
def get_report(client_id: str, request:  Request):
    # Connect to the SQLite database
    db_path = "database.db"  # Replace with the path to your SQLite database file
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query the database for the report with voice_analysis key
    query = "SELECT report FROM client_report WHERE client_id = ? AND report LIKE '%\"voice_analysis\"%'"
    cursor.execute(query, client_id)
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return {"error": "Report not found"}

    # Extract the report from the row
    report_data = row[0]

    conn.close()

    return {"client_id": client_id, "report": json.loads(report_data)}


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
async def create_client_report(client_report):
    query = """
        INSERT INTO client_report (client_id, report)
        VALUES (?, ?)
    """
    # parameters = (client_report.client_id, client_report.report)
    parameters = (client_report['client_id'], client_report['report'])
    try:
        cursor.execute(query, parameters)
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import openai

openai.api_key = "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"

prompt_msg = [
    {
       "role": "system",
      "content": "You are a helpful assistant. You will be helping an insurance agent who is learning to pitch\nYou will be given the following text:\nQuestion:..\nIdeal Answer : ...\nMy Answer:..\n\nYou need to holistically evaluate the My Answer with respective to Ideal Answer.\n\nproperly compare both and create a tabular json listing common and missing semantic concepts and entities.\n\nGive scores ( 0 to 10)  for [clarity , confidence, content, relevance] in format\n{{ quality: score}}\n\nGive appropriate detailed subjective comments in hinglish. Aap hinglish mai continue karo"
    },
    {
      "role": "user",
      "content": "Question: Health insurance plan ke liye recommended cover amount kitna hota hai?\nIdeal Answer: \nHealth insurance plan ke liye recommended cover amount generally 5 se 10 lakh ke beech hota hai. Yeh amount aapki personal needs, medical history, aur current healthcare costs par depend karta hai. Ek acchi health insurance plan mein aapko apni family aur apne aap ko sametne ke liye sufficient cover amount chunna chahiye. Agar aap family plan le rahe hain, toh 15 lakh tak ka cover amount bhi consider kar sakte hain. Cover amount ka chunav aapke future expenses, hospitalization costs, aur medical treatments ke hisab se kiya jana chahiye, taki aapko financial protection mile aur aap apne swasthya ki chinta se mukt rah sake.\nMy answer:\nWoh apke konse hospital aur konse type ka  hospital chaiye aur konsa treatment chaiye uske upar decide hota hai.  Par generally 5 lakh ke around hota hai."
    },
    {
      "role": "assistant",
      "content": "{\n  \"common\": [\n    \"health insurance plan\",\n    \"recommended cover amount\"\n  ],\n  \"missing\": [\n    \"personal needs\",\n    \"medical history\",\n    \"current healthcare costs\",\n    \"family\",\n    \"future expenses\",\n    \"hospitalization costs\",\n    \"medical treatments\",\n    \"financial protection\",\n    \"swasthya ki chinta\"\n  ]\n}\n\n{\n  \"quality\": {\n    \"clarity\": 5,\n    \"confidence\": 7,\n    \"content\": 3,\n    \"relevance\": 5\n  }\n}\n\nComments:\n- The answer lacks clarity and confidence as it does not provide a specific range for the recommended cover amount.\n- The content is lacking as it does not mention important factors such as personal needs, medical history, and current healthcare costs.\n- The relevance is average as it partially addresses the question but does not provide a comprehensive answer."
    },
    {
      "role": "user",
      "content": "Question: Kya alternative treatments included hote hai ?\nIdeal Answer :\nThe coverage for alternative medicine treatments works on the principle of full coverage up to the sum insured. If you opt for Ayurvedic, Homeopathic, or other alternative treatments, the insurer will reimburse the expenses incurred for these treatments, as long as the total amount claimed does not exceed the sum insured of your policy. It's a valuable feature that recognizes the growing importance of alternative healthcare approaches.\n\nMy Answer:\nSabhi type ke Ayurvedic aur Homeopathic treatment covered hai."
    },
    {
      "role": "assistant",
      "content": "{\n  \"common\": [\n    \"alternative treatments\"\n  ],\n  \"missing\": [\n    \"coverage\",\n    \"full coverage\",\n    \"sum insured\",\n    \"reimburse\",\n    \"expenses\",\n    \"policy\",\n    \"valuable feature\",\n    \"alternative healthcare approaches\"\n  ]\n}\n\n{\n  \"quality\": {\n    \"clarity\": 7,\n    \"confidence\": 8,\n    \"content\": 3,\n    \"relevance\": 7\n  }\n}\n\nComments:\n- The answer is clear and confident in stating that Ayurvedic and Homeopathic treatments are covered.\n- However, it lacks important information such as the coverage details, reimbursement process, and the recognition of alternative healthcare approaches as a valuable feature.\n- The relevance is decent as it partially addresses the question but does not provide a comprehensive answer."
    }
  ]


def evaluator_func(input_json):
  ideal_ans = input_json['transcript']['ideal_answer']
  my_answer = input_json['transcript']
  the_question = input_json['question']
  user_inp = f"Question:{the_question} Ideal Answer: {ideal_ans} My Answer: {my_answer}"
  user_prompt = {}
  user_prompt["role"] = "user"
  user_prompt["content"] = user_inp
  prompt_msg.append(user_prompt)
  response = openai.ChatCompletion.create(
  model="gpt-3.5-turbo-16k",
  messages=prompt_msg,
  temperature=0.45,
  max_tokens=1024,
  top_p=1,
  frequency_penalty=0.0,
  presence_penalty=0
)
  generated_texts = [
        choice.message["content"].strip() for choice in response["choices"]
    ]
  return generated_texts


def create_collated_report(client_id):
    # Retrieve the reports from the database using raw SQL
    query = "SELECT report FROM client_report where client_id=?"
    parameters = [client_id]
    cursor.execute(query, parameters)
    reports = cursor.fetchall()

    # Calculate the average of values with the same keys
    averages = defaultdict(list)
    for report_tuple in reports:
        report_json = report_tuple[0]  # Extract the JSON string from the tuple
        report = json.loads(report_json)  # Parse the JSON string into a dictionary
        for key, value in report.items():
            if key != 'feedback' and isinstance(value, (int, float)):
                averages[key].append(value)

    averaged_values = {key: sum(values) / len(values) for key, values in averages.items() if values}

    # Combine the feedback keys
    combined_feedback = defaultdict(list)
    for report_tuple in reports:
        report_json = report_tuple[0]  # Extract the JSON string from the tuple
        report = json.loads(report_json)  # Parse the JSON string into a dictionary
        feedback = report.get('feedback', {})  # Access the feedback dictionary from the report dictionary
        print("feed", feedback)
        for index, value in enumerate(feedback, start=1):
            key = f'feedback-{index}'
            value = value.replace('\n', '')
            value = value.strip()
            combined_feedback[key].append(value)

    judgers = {
        'speech_clarity': {
            'value': averaged_values.get('speech_clarity', 0),
            'judger': "Bad" if averaged_values.get('speech_clarity', 0) < 0.5 else "Good"
        },
        'tonality': {
            'value': averaged_values.get('tonality', None),
            'judger': "Good" if averaged_values.get('tonality', None) is not None else "Bad"
        },
        'speech_pitch': {
            'value': averaged_values.get('speech_pitch', 0),
            'judger': "Good" if averaged_values.get('speech_pitch', 0) > 0.2 else "Bad"
        },
        'speech_energy': {
            'value': averaged_values.get('speech_energy', 0),
            'judger': "Bad" if averaged_values.get('speech_energy', 0) < 0.1 else "Good"
        },
    }

    # Create the collated report
    collated_report = {
        'averages': judgers,
        'combined_feedback': combined_feedback,
    }

    return collated_report


audio_messages=[
    {
      "role": "system",
      "content": "You are a helpful assistant. You will recieve json like this: \naudio_scores = {\"speech_clarity\": { \"value\": -28.05926513671875,\"judger\": \"Bad\"},\"tonality\": {    \"value\": 654.1840743562444,    \"judger\": \"Good\"},\"speech_pitch\": {    \"value\": 228.89716410099348,    \"judger\": \"Good\"},\"speech_energy\": {\"value\": 0.02519330382347107,    \"judger\": \"Bad\"} }\n\n give constructive feedback. just mention the tips dont talk about the scores. Aur Hinglish mai bat kijiye."
    },
    {
      "role": "user",
      "content": "audio_scores = {\"speech_clarity\": {\"value\": -28.05926513671875,\"judger\": \"Bad\"},\"tonality\": {    \"value\": 654.1840743562444,    \"judger\": \"Good\"},\"speech_pitch\": {    \"value\": 228.89716410099348,    \"judger\": \"Good\"},\"speech_energy\": {    \"value\": 0.02519330382347107,    \"judger\": \"Bad\"} }"
    },
    {
      "role": "assistant",
      "content": "Aapke audio scores ke aadhar par, main kuch tips dena chahoonga:\n\n1. Speech clarity ko improve karne ke liye, aapko apni awaaz ko saaf aur sunaayi deni chahiye. Dhyaan dein ki aap har shabd ko sahi tarah se bol rahe hain aur apni baat ko samajhne waale logon tak asaani se pahuncha sakte hain.\n\n2. Tonality aapki acchi hai, iska matlab aapki awaaz mein ek acchi surili quality hai. Apne tonality ko maintain karte rahe aur apni baat ko aur bhi madhur banaye.\n\n3. Speech pitch aapki acchi hai, yani aapki awaaz ki uchaai kam yaadhota hai. Iss pitch par baat karna logon ko aapki baat sunne mein asaani aur samajhne mein madad karegi.\n\n4. Speech energy ko Sudharna jaruri hai. Iska matlab, aapko apni awaaz mein zyada energy aur jaan dalni chahi"
    }
  ]
summary_messages=[
    {
      "role": "system",
      "content": "You are a helpful assistant. You will be given a feedback json. Summarise the same into 5 actionable points  just in one sentence.for an insurance agent what he can improve in his pitch and how to improve it . The actionable points should be more on conversational skills and overall insurance knowledge. They are to the point.  The output is simple common man terms \n\n{\n\"feedback_1\":...,\n\"feedback_2\":..,\n}\n\nAap Hinglish mai bolte ho."
    },
    {
      "role": "user",
      "content": "{\n\"feedback_1\":''Your answer covers most of the common semantic concepts and entities mentioned in the ideal answer. However, it is missing some important points such as the consideration of a family plan, the availability of higher cover amounts for a family plan, the option of a 15 lakh cover amount, and the consideration of medical treatments. Overall, your answer provides a partial representation of the ideal answer, covering a significant portion of the information.',\n\"feedback_2\":\n  'From an outcome perspective, the ideal answer provides a more comprehensive and detailed response. It not only includes the range of recommended cover amounts but also factors in personal needs, medical history, current healthcare costs, family coverage, future expenses, hospitalization costs, and financial protection. Your answer, on the other hand, focuses on the decision-making process based on hospitals, treatment types, and a general coverage amount around 5 lakh. While it captures some relevant aspects, it lacks the comprehensive considerations mentioned in the ideal answer.'\n}"
    },
    {
      "role": "assistant",
      "content": "1. Include information about family plans and the availability of higher cover amounts for them.\n2. Mention the option of a 15 lakh cover amount.\n3. Consider the importance of medical treatments in the insurance pitch.\n4. Provide a more comprehensive response by considering personal needs, medical history, current healthcare costs, future expenses, and financial protection.\n5. Emphasize the importance of family coverage and hospitalization costs in the insurance pitch."
    }
  ]
def generate_summary_report(feedbacks,audio_scores):
  print("feeb", feedbacks, audio_scores)
  user_prompt = {}
  user_prompt["role"] = "user"
  user_prompt["content"] = str(feedbacks)
  summary_messages.append(user_prompt)
  response = openai.ChatCompletion.create(
  model="gpt-3.5-turbo-16k",
 messages = summary_messages,
  temperature=0.5,
  max_tokens=320,
  top_p=1,
  frequency_penalty=0,
  presence_penalty=0
)

  generated_texts = {}
  generated_texts['text_summary'] = response['choices'][0]['message']['content']
  user_inp = " ".join(str(audio_scores).split())
  user_prompt = {}
  user_prompt["role"] = "user"
  user_prompt["content"] = user_inp
  audio_messages.append(user_prompt)
  response = openai.ChatCompletion.create(
  model="gpt-3.5-turbo-16k",
  messages=audio_messages,
  temperature=1,
  max_tokens=256,
  top_p=1,
  frequency_penalty=0,
  presence_penalty=0
)
  generated_texts['audio_summary'] =response['choices'][0]['message']['content']
  return generated_texts