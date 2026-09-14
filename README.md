# Hayati — AI Digital One Health Surveillance Prototype

Hayati is a web-based health and One Health chatbot prototype. This upgraded version keeps the original safety-first architecture and adds two transparent research features:

1. **Possible-condition assessment** — identifies symptom patterns and ranks possible condition categories. It does **not** diagnose disease.
2. **Outbreak-risk surveillance signal** — aggregates structured reports by time, location, growth, and severity to flag unusual reporting activity. It does **not** predict a pandemic and does not replace epidemiological investigation.

## Stack
- FastAPI backend
- HTML/CSS/JavaScript web interface
- SQLite persistence
- Gemini Flash for general conversational health information
- Deterministic emergency classifier
- Explainable Python symptom-pattern and surveillance analytics

## Setup

```bash
cd hayati
python -m venv venv
# Windows PowerShell
venv\Scripts\Activate.ps1
pip install -e .
copy .env.example .env
# edit .env and add GEMINI_API_KEY
uvicorn hayati:app --reload
```

Open `http://127.0.0.1:8000/chat`.

## API
- `POST /api/v1/chat` — conversational health information + possible-condition assessment
- `POST /api/v1/surveillance/report` — record a structured surveillance report
- `GET /api/v1/surveillance/risk?window_days=7` — calculate the prototype surveillance risk signal
- `GET /api/v1/health` — health check
- `GET /api/v1/docs` — API documentation

### Example surveillance report

```json
{
  "location": "Edo State",
  "condition": "malaria-like illness",
  "severity": "moderate",
  "symptoms": ["fever", "headache", "chills"]
}
```

## Important limitations
This is a research prototype. The condition assessment is not clinically validated, and the surveillance score is not an epidemiological or pandemic-prediction model. Production use would require clinician/public-health validation, a larger verified knowledge base, privacy/security controls, authentication, human oversight, formal surveillance integration, and substantially more rigorous evaluation.

## v0.4 upgrade

Hayati now includes a medical-focused dashboard and patient continuity memory.

### New patient memory features
- Patient profile with optional name, age, sex, location, reported conditions, allergies, medications and notes.
- A stable browser patient ID keeps the same prototype patient record across new consultations on the same browser.
- Symptoms detected in chat are automatically saved to the patient's symptom history.
- The AI receives the patient's relevant recorded context during a consultation and is instructed to treat it as reported history, not as a diagnosis.
- New API endpoints are available under `/api/v1/patients`.

### Frontend
- Medical/clinical visual language with teal, white and navy palette.
- Consultation dashboard, patient memory and One Health surveillance views.
- Responsive desktop/tablet/mobile layout.
- Patient-context panel and remembered symptom list.

### Important production note
The current SQLite memory store is intended for development/prototyping. Do not place real identifiable patient records into this free Render prototype. A production release should use managed PostgreSQL, authentication, role-based access, encryption, retention/deletion controls and audit logs.
