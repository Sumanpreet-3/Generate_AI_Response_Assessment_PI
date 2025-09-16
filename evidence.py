# v2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Tuple
import os, re, uuid, tempfile, shutil, requests, base64
from openai import OpenAI
from dotenv import load_dotenv
import pandas as pd
import fitz
from PIL import Image
import openpyxl

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
    evidence_urls: Optional[List[str]] = []
    evidence_names: Optional[List[str]] = []

class SummaryResponse(BaseModel):
    summary: str

# File processing utilities
EXT_REGEX = re.compile(r"\.(png|jpe?g|pdf|xlsx?|xls)", re.IGNORECASE)

def download_s3_url(url: str, dest_dir: str) -> Tuple[str,str]:
    """Download file, infer extension, save, return (local_path, ext)"""
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise HTTPException(400, f"Failed to download {url}")
    # Try regex first
    m = EXT_REGEX.search(url)
    ext = m.group(1).lower() if m else None
    if not ext:
        # fallback to content-type
        ct = r.headers.get("Content-Type","")
        if "pdf" in ct: ext="pdf"
        elif "spreadsheet" in ct or "excel" in ct: ext="xlsx"
        elif "image/jpeg" in ct: ext="jpeg"
        elif "image/png" in ct: ext="png"
        else: ext="bin"
    fname = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(dest_dir, fname)
    with open(path,"wb") as f:
        for chunk in r.iter_content(1024*32): f.write(chunk)
    return path, ext

def process_image(fp: str) -> Tuple[str, str]:
    ext = os.path.splitext(fp)[1].lower()
    mime = "image/jpeg" if ext in ('.jpg', '.jpeg') else "image/png"
    data = base64.b64encode(open(fp, "rb").read()).decode()
    return mime, data

def process_excel(fp: str) -> str:
    xls = pd.ExcelFile(fp, engine='openpyxl')
    out = []
    for name in xls.sheet_names:
        df = xls.parse(name)
        out.append(f"Sheet: {name}\n{df.to_string()}")
    return "\n\n".join(out)

def process_pdf(fp: str) -> Tuple[str, List[str]]:
    doc = fitz.open(fp)
    txt = "".join(page.get_text() for page in doc)
    imgs = []
    for page in doc:
        for imginfo in page.get_images(full=True):
            xref = imginfo[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.width > 300 and pix.height > 300:
                imgp = f"{fp}_{xref}.png"
                pix.save(imgp)
                imgs.append(imgp)
            pix = None
    return txt, imgs

def process_files(paths: List[str]) -> Tuple[str, List[Tuple[str, str]]]:
    text = ""
    images = []
    for p in list(paths):
        low = p.lower()
        if low.endswith(('.png', '.jpg', '.jpeg')):
            images.append(process_image(p))
        elif low.endswith(('.xls', '.xlsx')):
            text += f"\n\n--- EXCEL {os.path.basename(p)} ---\n"
            text += process_excel(p)
        elif low.endswith('.pdf'):
            text += f"\n\n--- PDF {os.path.basename(p)} ---\n"
            pdf_txt, pdf_imgs = process_pdf(p)
            text += pdf_txt
            for ip in pdf_imgs:
                paths.append(ip)
    return text, images

def process_evidence_files(evidence_urls: List[str]) -> Tuple[str, List[Tuple[str, str]]]:
    """Process evidence files from URLs and return extracted text and images"""
    if not evidence_urls:
        return "", []
    
    # Create temporary directory
    temp_dir = os.path.join(tempfile.gettempdir(), "evidence_" + uuid.uuid4().hex)
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        local_paths = []
        for url in evidence_urls:
            try:
                path, ext = download_s3_url(url, temp_dir)
                local_paths.append(path)
            except Exception as e:
                print(f"Failed to download {url}: {e}")
                continue

        # Process all downloaded files
        text, images = process_files(local_paths)
        return text, images
    finally:
        # Cleanup temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        
    

@app.post("/generate_summary", response_model=SummaryResponse)
async def generate_summary(request: GenerateSummaryRequest):
    # Step 1: Build questionnaire from request
    print("Received request:", request.qas)
    questionnaire = "\n".join(
        [f"Q: {qa.text}\nA: {qa.userResponse or 'No answer provided'}" for qa in request.qas]
    )

    # Step 2: Process evidence files if provided
    evidence_context = ""
    evidence_images = []
    evidence_manifest = ""
    
    if request.evidence_urls:
        evidence_manifest = "\n\n## EVIDENCE FILES:\n" + "\n".join(
        [
            f"- [{i+1}] {request.evidence_names[i] if (request.evidence_names and i < len(request.evidence_names)) else os.path.basename(request.evidence_urls[i]).split('?')[0]}"
            for i in range(len(request.evidence_urls))
        ]
    )
        print(f"Processing {len(request.evidence_urls)} evidence files...")
        print(f"Evidence URLs:{evidence_manifest}")
        try:
            evidence_text, evidence_images = process_evidence_files(request.evidence_urls)
            if evidence_text:
                evidence_context = f"\n\n## EVIDENCE DOCUMENTATION:\n{evidence_text}"
            print(f"Evidence : {evidence_text}")
            print(f"Extracted evidence: {len(evidence_text)} chars text, {len(evidence_images)} images")
        except Exception as e:
            print(f"Error processing evidence files: {e}")
            evidence_context = "\n\n## EVIDENCE DOCUMENTATION:\n[Error processing evidence files]"

    # Step 3: Check for example in example_dict
    example = example_dict.get((request.control_id, request.asset_type))

    if example:
        # Use example's questionnaire and summary in the prompt
        example_q = "\n".join([
            f"Q: {q['text']}\nA: {q['userResponse'] or 'No answer provided'}" for q in example["questionnaire"]
        ])
        example_summary = example["summary"]
        prompt_text = f"""
        You are an expert PCI DSS auditor and consultant with deep knowledge of payment card industry data security standards. 

        ## Task

        You are being given:
        - a transcription of an interview (#Questionnaire#) with a client about the PCI DSS compliance of a specific control (#Control ID#),
        - extracted textual evidence from uploaded files (PDFs, Excel sheets, images) supplied in #Evidence Text# which must be analyzed,
        - the referenced images supplied in  #Evidence Images# which must be analyzed visually,
        - and contextual control metadata (#Control ID#, #Control Description#, #Requirement#, #Subrequirement#, #Asset Type#) below.
        The interview is in context of an Asset in the client organization of Asset Type specified below against #Asset Type#. Can you generate a bulleted summary of the interview 
        that is concise, brief and clear.Use ALL these inputs together (#Questionnaire#+ #Evidence Text# + #Evidence Images# + control metadata(#Control ID#,#Control Description#, #Requirement#, #Subrequirement#, #Asset Type#)) when producing the final output. 
        Treat the evidence files as primary source material: do not hallucinate facts that are not present in the interview or the evidence. Where you assert a point, attach the supporting evidence identifier(s) using the file names listed under #Evidence Files# in square brackets (e.g., [EVIDENCE: inventory.xlsx], [IMAGE: img_01]) so the QSA can quickly verify the claim.
        Each bullet point should be about each check list item that the QSA needs to check for compliance for this asset type and control.
        The objective is that the QSA can use this summary to quickly understand the compliance status of the control for this particular asset type.

        #Control ID#: {request.control_id}
        #Control Description#: {request.control_description}
        #Requirement#: {request.requirement_description}
        #Subrequirement#: {request.subrequirement_description}
        #Asset Type#: {request.asset_type}
        #Questionnaire#: {questionnaire}
        #Evidence Text# :{evidence_context}
        #Evidence Files#:{evidence_manifest}
        #Evidence Images#: [Please analyze the images provided with this prompt] 

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

        ## Response Template

       **Assessment Summary**: [-Exactly 100 words total across the bulleted list. 
        -Provide concise, objective bullets — each bullet should be a single short phrase or fragment (not full sentences) focused on a checklist item that helps the QSA decide compliance for this asset and control. 
        -Do NOT repeat the interview questions or full answers.
        -Include supporting evidence identifiers in square brackets ONLY if support the relevant bullet point, otherwise don't put this just mention the bullet point.Attach the supporting evidence identifier(s) using the file names listed under #Evidence Files# in square brackets.Example bullet: "- Remote admin disabled on internet-facing server [EVIDENCE: config.pdf; IMAGE: img_02]".]
       
        **Evidence Analysis**: 
            - **Evidence Sufficiency**: [Answer in one short sentence: SUFFICIENT | PARTIAL | INSUFFICIENT - Rate the completeness of evidence provided.]
            - **Missing / Ambiguous Evidence**: [Provide bullets listing *what additional evidence is required* if INSUFFICIENT or PARTIAL (e.g., logs for last 30 days, change control record, full scan report, original unredacted invoice).List any items (documents, screenshots, clarifications) missing from the provided evidence that are necessary to reach a firm conclusion. Keep to 1–4 bullets.]

        **Recommendation**: [IN PLACE | NOT IN PLACE | NOT TESTED | NOT APPLICABLE]

        **Key Justification**: [If the **Recommendation** is IN PLACE.Provide 2-3 bullet points explaining how the combination of responses, documentation, and evidence supports compliance. Reference specific evidence sources. Otherwise, this can be empty]

        **GAPS IDENTIFIED**: [If the **Recommendation** is NOT IN PLACE. Provide 2-3 bullet points explaining the gaps identified that need to be addressed for PCI compliance of this asset for the given control. Otherwise, this can be empty]

        ## Quality Guidelines
        - Be objective and evidence-based
        -**Evidence Integration**:
            - Correlate questionnaire responses with supporting documentation and visual evidence
            - Identify inconsistencies between stated practices and documented evidence
            - Evaluate whether evidence demonstrates both design and operational effectiveness
            - Note when evidence contradicts or supports interview responses
        - **Assessment Summary** should be concise, clear and bulleted. It should be objective and only contain data from interview. Do not hallucinate or provide your interpretation. Just report whats in the interview.
        - Use precise PCI DSS terminology
        - Focus on compliance-relevant findings
        - Avoid speculation or assumptions
        - Maintain professional, auditor-appropriate tone
        - Ensure recommendations align with PCI DSS standards

        ## Final note to the model
        Remember: 
        -integrate the uploaded evidences (text + images) with the questionnaire and control metadata. 
        -Explicitly state whether the provided evidence is sufficient to support the user's answers or whether more evidence is required. 
        -Where appropriate, suggest the *specific* evidence items that would resolve ambiguity or permit a definitive recommendation.

        """

        
    else:
        # Use default prompt
        prompt_text = f"""
        You are an expert PCI DSS auditor and consultant with deep knowledge of payment card industry data security standards. 

        ## Task

        You are being given:
        - a transcription of an interview (#Questionnaire#) with a client about the PCI DSS compliance of a specific control (#Control ID#),
        - extracted textual evidence from uploaded files (PDFs, Excel sheets, images) supplied in #Evidence Text# which must be analyzed,
        - the referenced images supplied in  #Evidence Images# which must be analyzed visually,
        - and contextual control metadata (#Control ID#, #Control Description#, #Requirement#, #Subrequirement#, #Asset Type#) below.
        The interview is in context of an Asset in the client organization of Asset Type specified below against #Asset Type#. Can you generate a bulleted summary of the interview 
        that is concise, brief and clear.Use ALL these inputs together (#Questionnaire#+ #Evidence Text# + #Evidence Images# + control metadata(#Control ID#,#Control Description#, #Requirement#, #Subrequirement#, #Asset Type#)) when producing the final output. 
        Treat the evidence files as primary source material: do not hallucinate facts that are not present in the interview or the evidence. Where you assert a point, attach the supporting evidence identifier(s) using the file names listed under #Evidence Files# in square brackets(e.g., [EVIDENCE: inventory.xlsx], [IMAGE: img_01]) so the QSA can quickly verify the claim.
        Each bullet point should be about each check list item that the QSA needs to check for compliance for this asset type and control.
        The objective is that the QSA can use this summary to quickly understand the compliance status of the control for this particular asset type.

        #Control ID#: {request.control_id}
        #Control Description#: {request.control_description}
        #Requirement#: {request.requirement_description}
        #Subrequirement#: {request.subrequirement_description}
        #Asset Type#: {request.asset_type}
        #Questionnaire#: {questionnaire}
        #Evidence Text# :{evidence_context}
        #Evidence Files#:{evidence_manifest}
        #Evidence Images#: [Please analyze the images provided with this prompt] 

        This summary will be used by Qualified Security Assessors (QSAs) to evaluate compliance of this asset with the given control of PCI DSS standards.
        Your task is to extract the key points from the interview that will help QSAs determine compliance status.
        In addition to the bulleted summary also provide your recommendation on whether the asset is compliant with the control or not. The recommendation should be one of the following:
        - **IN PLACE**: Control is properly implemented and functioning as required
        - **NOT IN PLACE**: Control is missing, inadequate, or not functioning properly
        - **NOT TESTED**: Insufficient information to determine compliance status
        - **NOT APPLICABLE**: Control requirement does not apply to current environment

        Use professional language suitable for QSA(Qualified Security Assessor) to facilitate their decision making process in compliance assessments.

        ## Response Template

        **Assessment Summary**: [-Exactly 100 words total across the bulleted list. 
        -Provide concise, objective bullets — each bullet should be a single short phrase or fragment (not full sentences) focused on a checklist item that helps the QSA decide compliance for this asset and control. 
        -Do NOT repeat the interview questions or full answers.
        -Include supporting evidence identifiers in square brackets ONLY if support the relevant bullet point, otherwise don't put this just mention the bullet point.Attach the supporting evidence identifier(s) using the file names listed under #Evidence Files# in square brackets.Example bullet: "- Remote admin disabled on internet-facing server [EVIDENCE: config.pdf; IMAGE: img_02]".]
       
        **Evidence Analysis**: 
            - **Evidence Sufficiency**: [Answer in one short sentence: SUFFICIENT | PARTIAL | INSUFFICIENT - Rate the completeness of evidence provided.]
            - **Missing / Ambiguous Evidence**: [Provide bullets listing *what additional evidence is required* if INSUFFICIENT or PARTIAL (e.g., logs for last 30 days, change control record, full scan report, original unredacted invoice).List any items (documents, screenshots, clarifications) missing from the provided evidence that are necessary to reach a firm conclusion. Keep to 1–4 bullets.]

        **Recommendation**: [IN PLACE | NOT IN PLACE | NOT TESTED | NOT APPLICABLE]

        **Key Justification**: [If the **Recommendation** is IN PLACE.Provide 2-3 bullet points explaining how the combination of responses, documentation, and evidence supports compliance. Reference specific evidence sources. Otherwise, this can be empty]

        **GAPS IDENTIFIED**: [If the **Recommendation** is NOT IN PLACE. Provide 2-3 bullet points explaining the gaps identified that need to be addressed for PCI compliance of this asset for the given control. Otherwise, this can be empty]

        ## Quality Guidelines
        - Be objective and evidence-based
        -**Evidence Integration**:
            - Correlate questionnaire responses with supporting documentation and visual evidence
            - Identify inconsistencies between stated practices and documented evidence
            - Evaluate whether evidence demonstrates both design and operational effectiveness
            - Note when evidence contradicts or supports interview responses
        - **Assessment Summary** should be concise, clear and bulleted. It should be objective and only contain data from interview. Do not hallucinate or provide your interpretation. Just report whats in the interview.
        - Use precise PCI DSS terminology
        - Focus on compliance-relevant findings
        - Avoid speculation or assumptions
        - Maintain professional, auditor-appropriate tone
        - Ensure recommendations align with PCI DSS standards
        

        ## Final note to the model
        Remember: 
        -integrate the uploaded evidences (text + images) with the questionnaire and control metadata. 
        -Explicitly state whether the provided evidence is sufficient to support the user's answers or whether more evidence is required. 
        -Where appropriate, suggest the *specific* evidence items that would resolve ambiguity or permit a definitive recommendation.

        """
        

    try:
        # Step 4: Prepare messages for OpenAI API call
        if evidence_images:
            # Use the chat completions API with multimodal support
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert PCI DSS auditor and consultant with deep knowledge of payment card industry data security standards."
                }
            ]
            
            # User message with text and images
            user_content = [{"type": "text", "text": prompt_text}]
            
            # Add images
            for mime_type, base64_data in evidence_images:
               
                user_content.append({
                  "type": "image_url",
                  "image_url": {
                      "url": f"data:{mime_type};base64,{base64_data}"
                    }
                    })
                
            # print(f"Prepared {user_content} images for OpenAI input.")

            
            messages.append({
                "role": "user",
                "content": user_content
            })
            
            # Use chat completions for multimodal
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.2
            )
            
            summary_text = response.choices[0].message.content.strip()
            
        else:
            # Use chat completions API for text-only (no responses API)
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert PCI DSS auditor and consultant with deep knowledge of payment card industry data security standards."
                },
                {
                    "role": "user", 
                    "content": prompt_text
                }
            ]
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.2
            )
            
            summary_text = response.choices[0].message.content.strip()

        return SummaryResponse(summary=summary_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)