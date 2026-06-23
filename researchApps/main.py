from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import fitz  # PyMuPDF
from groq import Groq
import os

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL = "llama-3.3-70b-versatile"

app = FastAPI(title="Research Paper Summarizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def summarize_with_groq(text: str) -> str:
    client = Groq(api_key=GROQ_API_KEY)

    # Truncate text to avoid token limits while keeping meaningful content
    truncated = text[:12000] if len(text) > 12000 else text

    prompt = (
        "You are an expert academic summarizer. Read the following research paper text and "
        "provide a concise, single-paragraph summary (no more than 5-6 sentences). "
        "The summary must cover: the main research objective, the methodology used, "
        "the key findings, and the significance or conclusion. "
        "Do not use bullet points or headings — write it as one coherent paragraph.\n\n"
        f"Research Paper:\n{truncated}"
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
    )

    return response.choices[0].message.content.strip()


@app.get("/")
def serve_index():
    return FileResponse("static/index.html")


@app.post("/summarize")
async def summarize(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        text = extract_text_from_pdf(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {str(e)}")

    if len(text) < 100:
        raise HTTPException(status_code=422, detail="PDF has too little extractable text (may be scanned/image-only).")

    try:
        summary = summarize_with_groq(text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

    return {"filename": file.filename, "summary": summary}
