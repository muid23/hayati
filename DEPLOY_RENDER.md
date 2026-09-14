# Hayati — free Render deployment

The frontend is served by the same FastAPI application, so browser requests use the current site origin and call `/api/v1/chat`.

## Render settings
- Service type: Web Service
- Plan: Free
- Build command: `pip install .`
- Start command: `uvicorn hayati:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/v1/health`
- Python: 3.14.3
- `GEMINI_API_KEY`: add your Gemini API key as a secret environment variable
- `GEMINI_MODEL`: `gemini-2.5-flash`

The app also supports WebSocket chat at `/api/v1/ws/chat`.

## Important free-host limitation
Hayati currently stores sessions and surveillance reports in SQLite. Render Free services have an ephemeral filesystem, so the SQLite database can be lost when the service restarts, spins down, or redeploys. For a real deployment, move the database to a persistent managed database such as Postgres.
