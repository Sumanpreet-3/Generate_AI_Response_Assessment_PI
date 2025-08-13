from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
# Initialize client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# OPEN_AI_KEY= fetch_secrets()
# client = OpenAI(api_key=OPEN_AI_KEY)


app = FastAPI(title="PCI DSS QSA Assessment API")

class QAItem(BaseModel):
    text: str
    userResponse: str

class SummaryResponse(BaseModel):
    summary: str

@app.post("/generate_summary", response_model=SummaryResponse)
async def generate_summary(qas: List[QAItem]):
    # Step 1: Build prompt from given questions and answers
    qa_text = "\n".join(
        [f"Q: {qa.text}\nA: {qa.userResponse or 'No answer provided'}"
         for qa in qas]
    )

    prompt = f"""
        You are a PCI DSS expert auditor (QSA). Based on the following Questions and Answers, create a short summary (max 100 words) 
        Highlight only the most important points and keywords by making them **bold**.
        Do not include any filler text or unnecessary information.

        Questions & Answers:
        {qa_text}
    """

    try:
        response = client.responses.create(
            model="gpt-4o",  
            input=prompt,
            temperature=0.2
        )

        summary_text = response.output_text.strip()

        return SummaryResponse(summary=summary_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)
 