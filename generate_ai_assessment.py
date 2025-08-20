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

class GenerateSummaryRequest(BaseModel):
    qas: List[QAItem]
    control_id: str
    control_description: str
    asset_type: str

class SummaryResponse(BaseModel):
    summary: str
    

@app.post("/generate_summary", response_model=SummaryResponse)
async def generate_summary(request: GenerateSummaryRequest):
    
    # Step 1: Build prompt from given questions and answers
    questionnaire = "\n".join(
        [f"Q: {qa.text}\nA: {qa.userResponse or 'No answer provided'}"
         for qa in request.qas]
    )

    # Step 2: Create the prompt with control details
    prompt = f"""
You are an expert PCI DSS auditor and consultant with deep knowledge of payment card industry data security standards. 

## Task
Analyze control implementations and Generate a professional,actionable assessment summary based on the following input data:
Control ID: {request.control_id}
Control Description: {request.control_description}
Asset Type: {request.asset_type}
Questionnaire: {questionnaire}
This summary will be used by Qualified Security Assessors (QSAs) to evaluate compliance with PCI DSS standards.
Your task is to synthesize the provided control information(Control ID and Control Description),Asset Type and Questionnaire to help QSAs determine compliance status.
And provide a clear recommendation based on the analysis that the QSA can use in their assessment report.
Use professional language suitable for QSA(Qualified Security Assessor) to facilitate their decision making process in compliance assessments.

## Input Data Format
**Control ID**: [PCI DSS control identifier, e.g., 1.1.1]
**Control Description**: [Detailed control description text]
**Asset Type**: [Systems, applications, network components, or processes in scope]
**Questionnaire**: [contains the question and client response pairs related to the control]

## Output Requirements

### Summary Format (Exactly 100 words)
Provide a concise assessment summary that includes:
- Current state of control implementation
- Technical and procedural findings
- Basis for the recommendation

### Recommendation Categories
Select ONE of the following:
- **IN PLACE**: Control is properly implemented and functioning as required
- **OUT OF PLACE**: Control is missing, inadequate, or not functioning properly
- **NOT TESTED**: Insufficient information to determine compliance status
- **NOT APPLICABLE**: Control requirement does not apply to current environment

## Response Template

**Assessment Summary**: [Exactly 100 words analyzing the control implementation based on Asset Type and Questionnaire, focusing on compliance ]

**Recommendation**: [IN PLACE | OUT OF PLACE | NOT TESTED | NOT APPLICABLE]

**Key Justification**: [2-3 bullet points explaining the recommendation basis]

## Quality Guidelines
- Be objective and evidence-based
- Use precise PCI DSS terminology
- Focus on compliance-relevant findings
- Avoid speculation or assumptions
- Maintain professional, auditor-appropriate tone
- Ensure recommendations align with PCI DSS standards



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
 