from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
# Initialize client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# Import example_dict from examples.py
from examples import example_dict
app = FastAPI(title="PCI DSS QSA Assessment API")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QAItem(BaseModel):
    text: str
    userResponse: str

class GenerateSummaryRequest(BaseModel):
    qas: List[QAItem]
    control_id: str
    control_description: str
    asset_type: str
    requirement_description: str
    subrequirement_description: str
class SummaryResponse(BaseModel):
    summary: str

@app.post("/generate_summary", response_model=SummaryResponse)
async def generate_summary(request: GenerateSummaryRequest):
    # Step 1: Build questionnaire from request
    questionnaire = "\n".join(
        [f"Q: {qa.text}\nA: {qa.userResponse or 'No answer provided'}" for qa in request.qas]
    )

    # Step 2: Check for example in example_dict
    example = example_dict.get((request.control_id, request.asset_type))

    if example:
        # Use example's questionnaire and summary in the prompt
        example_q = "\n".join([
            f"Q: {q['text']}\nA: {q['userResponse'] or 'No answer provided'}" for q in example["questionnaire"]
        ])
        example_summary = example["summary"]
        prompt = f"""
        You are an expert PCI DSS auditor and consultant with deep knowledge of payment card industry data security standards.

        ## Task

        You are being given transcription of an interview #Questionnaire# with a client regarding the PCI DSS compliance of a specific control specified against #Control ID# below.
        The interview is in context of an Asset in the client organization of Asset Type specified below against #Asset Type#. Can you generate a bulleted summary of the interview that is concise, brief and clear.
        Each bullet point should be about each check list item that the QSA needs to check for compliance for this asset type and control.
        The objective is that the QSA can use this summary to quickly understand the compliance status of the control for this particular asset type.
        Some more context is about the #Requirement#, #Subrequirement# and  #Control Description#, of PCI DSS framework, that this control falls in is provided below.

        #Control ID#: {request.control_id}
        #Control Description#: {request.control_description}
        #Requirement#: {request.requirement_description}
        #Subrequirement#: {request.subrequirement_description}
        #Asset Type#: {request.asset_type}
        #Questionnaire#: {questionnaire}

        ## Example
        Here is an example for a similar control and asset type:
        Example Questionnaire:
        {example_q}
        Example Summary:
        {example_summary}

        This summary will be used by Qualified Security Assessors (QSAs) to evaluate compliance of this asset with the given control of PCI DSS standards.
        Your task is to extract the key points from the interview that will help QSAs determine compliance status.
        In addition to the bulleted summary also provide your recommendation on whether the asset is compliant with the control or not. The recommendation should be one of the following:
        - **IN PLACE**: Control is properly implemented and functioning as required
        - **NOT IN PLACE**: Control is missing, inadequate, or not functioning properly
        - **NOT TESTED**: Insufficient information to determine compliance status
        - **NOT APPLICABLE**: Control requirement does not apply to current environment

        Use professional language suitable for QSA(Qualified Security Assessor) to facilitate their decision making process in compliance assessments.

        ## Input Data Format
        **Control ID**: [PCI DSS control identifier, e.g., 1.1.1]
        **Control Description**: [Detailed control description text]
        **Requirement**: [PCI DSS requirement description text for the control]
        **Subrequirement**: [PCI DSS subrequirement description text for the control]
        **Asset Type**: [Systems, applications, network components, or processes in scope]
        **Questionnaire**: [contains the question and client response pairs related to the control]

        ## Output Requirements

        ## Response Template

        **Assessment Summary**: [Exactly 100 words of bulleted list with each bullet giving a key point from the interview that is relevant determining the compliance status in context of the given asset and control, Do not repeat the questions or answers. Do not maintain proper sentences, Just provide the key points in bulleted list format. So that the QSA can quickly understand the compliance status of the control for this particular asset type.]

        **Recommendation**: [IN PLACE | OUT OF PLACE | NOT TESTED | NOT APPLICABLE]

        **Key Justification**: [If the **Recommendation** is IN PLACE. Provide 2-3 bullet points explaining the recommendation basis. Otherwise, this can be empty]

        **GAPS IDENTIFIED**: [If the **Recommendation** is NOT IN PLACE. Provide 2-3 bullet points explaining the gaps identified that need to be addressed for PCI compliance of this asset for the given control. Otherwise, this can be empty]

        ## Quality Guidelines
        - Be objective and evidence-based
        - **Assessment Summary** should be concise, clear and bulleted. It should be objective and only contain data from interview. Do not hallucinate or provide your interpretation. Just report whats in the interview.
        - Use precise PCI DSS terminology
        - Focus on compliance-relevant findings
        - Avoid speculation or assumptions
        - Maintain professional, auditor-appropriate tone
        - Ensure recommendations align with PCI DSS standards
        """
    else:
        # Use default prompt
        prompt = f"""
        You are an expert PCI DSS auditor and consultant with deep knowledge of payment card industry data security standards. 

        ## Task

        You are being given transcription of an interview #Questionnaire# with a client regarding the PCI DSS compliance of a specific control specified against #Control ID# below.
        The interview is in context of an Asset in the client organization of Asset Type specified below against #Asset Type#. Can you generate a bulleted summary of the interview 
        that is concise, brief and clear. Each bullet point should be about each check list item that the QSA needs to check for compliance for this asset type and control.
        The objective is that the QSA can use this summary to quickly understand the compliance status of the control for this particular asset type.
        Some more context is about the #Requirement#, #Subrequirement# and  #Control Description#, of PCI DSS framework, that this control falls in is provided below.

        #Control ID#: {request.control_id}
        #Control Description#: {request.control_description}
        #Requirement#: {request.requirement_description}
        #Subrequirement#: {request.subrequirement_description}
        #Asset Type#: {request.asset_type}
        #Questionnaire#: {questionnaire}

        This summary will be used by Qualified Security Assessors (QSAs) to evaluate compliance of this asset with the given control of PCI DSS standards.
        Your task is to extract the key points from the interview that will help QSAs determine compliance status.
        In addition to the bulleted summary also provide your recommendation on whether the asset is compliant with the control or not. The recommendation should be one of the following:
        - **IN PLACE**: Control is properly implemented and functioning as required
        - **NOT IN PLACE**: Control is missing, inadequate, or not functioning properly
        - **NOT TESTED**: Insufficient information to determine compliance status
        - **NOT APPLICABLE**: Control requirement does not apply to current environment

        Use professional language suitable for QSA(Qualified Security Assessor) to facilitate their decision making process in compliance assessments.

        ## Input Data Format
        **Control ID**: [PCI DSS control identifier, e.g., 1.1.1]
        **Control Description**: [Detailed control description text]
        **Requirement**: [PCI DSS requirement description text for the control]
        **Subrequirement**: [PCI DSS subrequirement description text for the control]
        **Asset Type**: [Systems, applications, network components, or processes in scope]
        **Questionnaire**: [contains the question and client response pairs related to the control]

        ## Output Requirements

        ## Response Template

        **Assessment Summary**: [Exactly 100 words of bullted list with each bullet giving a key point from the interview that is relevant determining the compliance status in context of the given asset and control, Do not repeat the questions or answers.Do not maintain proper sentences, Just provide the key points in bulleted list format.So that the QSA can quickly understand the compliance status of the control for this particular asset type.]

        **Recommendation**: [IN PLACE | OUT OF PLACE | NOT TESTED | NOT APPLICABLE]

        **Key Justification**: [If the **Recommendation** is IN PLACE. Provide 2-3 bullet points explaining the recommendation basis. Otherwise, this can be empty]

        **GAPS IDENTIFIED**: [If the **Recommendation** is NOT IN PLACE. Provide 2-3 bullet points explaining the gaps identifiedthat need to be addressed for PCI compliance of this asset for the given control. Otherwise, this can be empty]

        ## Quality Guidelines
        - Be objective and evidence-based
        - **Assessment Summary** should be concise, clear and bulleted. It should be objective and only contain data from interview. Do not hallucinate or provide your interpretation. Just report whats in the interview.
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
 