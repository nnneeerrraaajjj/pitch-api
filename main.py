import os
from fastapi import FastAPI, UploadFile, Form, File, HTTPException, Request
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
        "question": cal,
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
    print(cal, type(cal))
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
      "content": "You are an instructor. Evaluating insurance sales pitch related questions. Compare ideal answer and my answer. Compare the two answers and create a json listing common and missing semantic concepts in the form of entities in a json output. Give a subjective outcome based comparison\n\nTalk in Hinglish and the feedback should be understood by common man \n\nGive an overall score out of 5, clarity score out 5.\n"
    },
    {
      "role": "user",
      "content": "Ideal  Answer : While this policy has several beneficial features, it's important to note a couple of limitations. Firstly, there is a long waiting period of 4 years for coverage of pre-existing diseases such as diabetes and cardiovascular problems. It's worth considering that some policies may offer shorter waiting periods, such as 2 years, for coverage of pre-existing conditions.\n\nMy Answer: Is plan mai 4 saal ka waiting period pre existing disease ka cover chalu hone keliye. Kuch plan sirf 2 saal ka dete hai joki kum hai."
    },
    {
      "role": "assistant",
      "content": "{\n  \"Common Concepts/Entities\": [\n    \"Recommended cover amount\",\n    \"Personal needs\",\n    \"Medical history\",\n    \"Current healthcare costs\",\n    \"Sufficient cover amount\",\n    \"Family coverage\",\n    \"Future expenses\",\n    \"Hospitalization costs\",\n    \"Financial protection\"\n  ],\n  \"Missing Concepts/Entities in Your Answer\": [\n    \"Consideration of family plan\",\n    \"Higher cover amount for family plan\",\n    \"15 lakh cover amount option\",\n    \"Medical treatments\"\n  ]\n}\nYour answer covers most of the common semantic concepts and entities mentioned in the ideal answer. However, it is missing some important points such as the consideration of a family plan, the availability of higher cover amounts for a family plan, the option of a 15 lakh cover amount, and the consideration of medical treatments. Overall, your answer provides a partial representation of the ideal answer, covering a significant portion of the information. \nSubjective Outcome-Based Comparison:\n\nFrom an outcome perspective, the ideal answer provides a more comprehensive and detailed response. It not only includes the range of recommended cover amounts but also factors in personal needs, medical history, current healthcare costs, family coverage, future expenses, hospitalization costs, and financial protection. Your answer, on the other hand, focuses on the decision-making process based on hospitals, treatment types, and a general coverage amount around 5 lakh. While it captures some relevant aspects, it lacks the comprehensive considerations mentioned in the ideal answer.\n\nConsidering the outcome-based subjective comparison, the ideal answer provides a more thorough and informative response, covering a broader range of relevant details and considerations for selecting a health insurance plan.\n\nOverall score is 3.5. out of 5. Clarity 4 out 5"
    }
  ]


def evaluator_func(input_json):
  print("pinr", input_json)
  ideal_ans = input_json['transcript']['ideal_answer']
  my_answer = input_json['transcript']['transcript']
  user_inp = f"Ideal Answer: {ideal_ans} My Answer: {my_answer}"
  user_prompt = {}
  user_prompt["role"] = "user"
  user_prompt["content"] = user_inp
  prompt_msg.append(user_prompt)
  response = openai.ChatCompletion.create(
  model="gpt-3.5-turbo",
  messages=prompt_msg,
  temperature=0.45,
  max_tokens=300,
  top_p=1,
  frequency_penalty=0.3,
  presence_penalty=0
)
  generated_texts = [
        choice.message["content"].strip() for choice in response["choices"]
    ]
  return generated_texts


def create_collated_report(client_id):
    # Retrieve the reports from the database using raw SQL
    query = "SELECT report FROM client_report where client_id=?"
    parameters = client_id
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
      "content": "You are a helpful assistant. You will be given a feedback json. Summarise the same into 5 actionable points for an insurance agent what he can improve in his pitch and how to improve it . The actionable points should be more on conversational skills and overall insurance knowledge. They are to the point.  The output is simple common man terms \n\n{\n\"feedback_1\":''Your answer covers most of the common semantic concepts and entities mentioned in the ideal answer. However, it is missing some important points such as the consideration of a family plan, the availability of higher cover amounts for a family plan, the option of a 15 lakh cover amount, and the consideration of medical treatments. Overall, your answer provides a partial representation of the ideal answer, covering a significant portion of the information.',\n\"feedback_2\":\n  'From an outcome perspective, the ideal answer provides a more comprehensive and detailed response. It not only includes the range of recommended cover amounts but also factors in personal needs, medical history, current healthcare costs, family coverage, future expenses, hospitalization costs, and financial protection. Your answer, on the other hand, focuses on the decision-making process based on hospitals, treatment types, and a general coverage amount around 5 lakh. While it captures some relevant aspects, it lacks the comprehensive considerations mentioned in the ideal answer.'\n}\n\nAap Hinglish mai bolte ho."
    },
    {
      "role": "user",
      "content": "{\n\"feedback_1\":''Your answer covers most of the common semantic concepts and entities mentioned in the ideal answer. However, it is missing some important points such as the consideration of a family plan, the availability of higher cover amounts for a family plan, the option of a 15 lakh cover amount, and the consideration of medical treatments. Overall, your answer provides a partial representation of the ideal answer, covering a significant portion of the information.',\n\"feedback_2\":\n  'From an outcome perspective, the ideal answer provides a more comprehensive and detailed response. It not only includes the range of recommended cover amounts but also factors in personal needs, medical history, current healthcare costs, family coverage, future expenses, hospitalization costs, and financial protection. Your answer, on the other hand, focuses on the decision-making process based on hospitals, treatment types, and a general coverage amount around 5 lakh. While it captures some relevant aspects, it lacks the comprehensive considerations mentioned in the ideal answer.'\n}"
    },
    {
      "role": "assistant",
      "content": "Yahaan 5 actionable points hai aapke insurance pitch ko behtar banane ke liye:\n\n1. Parivaar yojana ke baare mein jaankari shaamil karein: Apne pitch mein parivaar coverage ke fayde aur upalabdh vikalp ko highlight karein. Samjhaayein ki parivaar yojana kitni adhik cover amount aur behtar vittiyak suraksha pradaan kar sakti hai.\n\n2. Adhik cover amount ke baare mein batayein: 15 lakh cover amount ka vikalp ko pramukhata dein, jisse graahakon ko samajh mein aaye ki unhein kitne level ki suraksha chunne ka vikalp hai.\n\n3. Chikitsa upachaar par vichar karein: Insurance yojana chunne par alag-alag chikitsa upachaaron aur unke kharche ke baare mein sochne ka zikr karein. Graahakon ko samjhaayein ki unki suraksha ke liye kis tarah ke chikitsa upachaar shamil hain.\n\n4. Vyaktigat zaroorat par dhyaan dein: Apne pitch mein vyaktigat zarooraton, aapke graahakon ki medical history, aur vartaman swasthya mein aane wale kharche ke ba"
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