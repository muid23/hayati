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
