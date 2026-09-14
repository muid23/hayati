"""Hayati AI One Health surveillance chatbot prototype."""

from typing import Literal
import uuid

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from .classifier import classify
from .gemini_client import ask_gemini, stream_gemini_async
from .risk_engine import assess_possible_conditions, outbreak_risk

app = FastAPI(title="Hayati", version="0.4.0", openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs", redoc_url="/api/v1/redoc")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
def home():
    return FileResponse("static/index.html")

@app.get("/chat", include_in_schema=False)
def chat_page():
    return FileResponse("static/index.html")

EMERGENCY_REPLY = (
    "Based on what you've described, this could be a medical emergency. "
    "Please call your local emergency number or go to the nearest emergency "
    "department right away. This assistant cannot provide emergency care."
)

@app.on_event("startup")
def on_startup():
    db.init_db()

class ChatRequest(BaseModel):
    session_id: str | None = None
    patient_id: str | None = None
    message: str = Field(min_length=1, max_length=8000)

class ChatResponse(BaseModel):
    session_id: str
    patient_id: str
    reply: str
    triage_level: str
    matched_flags: list[str]
    assessment: dict | None = None
    memory: dict | None = None

class PatientRequest(BaseModel):
    patient_id: str | None = None
    name: str = Field(default="Guest Patient", max_length=120)
    age: int | None = Field(default=None, ge=0, le=130)
    sex: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=120)
    conditions: list[str] = Field(default_factory=list, max_length=30)
    allergies: list[str] = Field(default_factory=list, max_length=30)
    medications: list[str] = Field(default_factory=list, max_length=30)
    notes: str = Field(default="", max_length=2000)

@app.post("/api/v1/patients")
def create_patient(req: PatientRequest):
    patient_id = req.patient_id or str(uuid.uuid4())
    patient = db.get_patient(patient_id)
    data = req.model_dump(exclude={"patient_id"})
    return db.update_patient(patient_id, data) if patient else db.create_patient(patient_id, data)

@app.get("/api/v1/patients/{patient_id}")
def get_patient(patient_id: str):
    return db.get_patient_memory(patient_id)

@app.patch("/api/v1/patients/{patient_id}")
def update_patient(patient_id: str, req: PatientRequest):
    return db.update_patient(patient_id, req.model_dump(exclude={"patient_id"}, exclude_unset=True))

@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    patient_id = req.patient_id or str(uuid.uuid4())
    db.ensure_patient(patient_id)
    db.ensure_session(session_id, patient_id)
    history = db.get_history(session_id)
    triage = classify(req.message)
    db.log_message(session_id, "user", req.message, triage["level"], triage["matched"])
    assessment = assess_possible_conditions(req.message)
    symptoms = assessment.get("symptoms_detected", [])
    db.add_symptoms(patient_id, session_id, symptoms, req.message, assessment.get("duration_detected"))
    memory = db.get_patient_memory(patient_id)

    if triage["level"] == "emergency":
        reply = EMERGENCY_REPLY
    else:
        reply = ask_gemini(history, req.message, memory)
        if assessment["results"]:
            top = assessment["results"][0]
            reply += (
                f"\n\nPossible pattern to discuss with a clinician: {top['condition']} "
                f"({top['score']}% symptom-pattern match). This is not a diagnosis and testing may be needed."
            )

    db.log_message(session_id, "assistant", reply)
    return ChatResponse(session_id=session_id, patient_id=patient_id, reply=reply, triage_level=triage["level"], matched_flags=triage["matched"], assessment=assessment, memory=memory)

class ReportRequest(BaseModel):
    session_id: str | None = None
    location: str = Field(min_length=2, max_length=120)
    condition: str | None = Field(default=None, max_length=120)
    severity: Literal["low", "moderate", "high", "severe", "emergency", "unknown"] = "unknown"
    symptoms: list[str] = Field(default_factory=list, max_length=30)

@app.post("/api/v1/surveillance/report")
def create_report(req: ReportRequest):
    session_id = req.session_id or str(uuid.uuid4())
    db.ensure_session(session_id)
    db.add_surveillance_report(session_id, req.location, req.condition, req.severity, req.symptoms)
    return {"status": "recorded", "message": "Report recorded for surveillance analysis. This does not confirm an outbreak.", "session_id": session_id}

@app.get("/api/v1/surveillance/risk")
def surveillance_risk(window_days: int = 7):
    if window_days < 1 or window_days > 90:
        return {"error": "window_days must be between 1 and 90"}
    return outbreak_risk(db.get_surveillance_reports(), window_days)

@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": "0.4.0", "memory": "enabled"}

@app.websocket("/api/v1/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            session_id = data.get("session_id") or str(uuid.uuid4())
            patient_id = data.get("patient_id") or str(uuid.uuid4())
            message = data["message"]
            db.ensure_patient(patient_id)
            db.ensure_session(session_id, patient_id)
            history = db.get_history(session_id)
            triage = classify(message)
            db.log_message(session_id, "user", message, triage["level"], triage["matched"])
            assessment = assess_possible_conditions(message)
            db.add_symptoms(patient_id, session_id, assessment.get("symptoms_detected", []), message, assessment.get("duration_detected"))
            memory = db.get_patient_memory(patient_id)
            await websocket.send_json({"type": "session", "session_id": session_id, "patient_id": patient_id, "memory": memory})
            if triage["level"] == "emergency":
                await websocket.send_json({"type": "chunk", "text": EMERGENCY_REPLY})
                db.log_message(session_id, "assistant", EMERGENCY_REPLY)
                await websocket.send_json({"type": "done", "triage_level": "emergency", "matched_flags": triage["matched"]})
                continue
            parts = []
            async for chunk in stream_gemini_async(history, message, memory):
                if isinstance(chunk, dict) and "error" in chunk:
                    await websocket.send_json({"type": "error", "detail": chunk["error"]})
                    break
                parts.append(chunk)
                await websocket.send_json({"type": "chunk", "text": chunk})
            db.log_message(session_id, "assistant", "".join(parts))
            await websocket.send_json({"type": "done", "triage_level": "routine", "matched_flags": triage["matched"], "assessment": assessment})
    except WebSocketDisconnect:
        pass
