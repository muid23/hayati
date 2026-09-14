FROM python:3.14-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

CMD sh -c 'uvicorn hayati:app --host 0.0.0.0 --port ${PORT}'
