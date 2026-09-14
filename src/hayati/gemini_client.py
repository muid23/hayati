import asyncio
import os
import threading
from collections.abc import AsyncIterator, Iterator
from typing import Any
from google import genai

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

SYSTEM_PROMPT = """You are Hayati, a general health information assistant focused on One Health.
You are NOT a doctor and must not diagnose or claim certainty.
- Explain possibilities in simple, natural language.
- Do not present a symptom-pattern score as a diagnosis.
- Encourage appropriate professional care for real health concerns.
- If something sounds serious, say so plainly and recommend prompt in-person care.
- Keep normal answers concise (3-6 sentences) unless the user asks for more detail.
- When patient memory is supplied, use it only as context. Clearly distinguish what the patient reported from anything confirmed by a clinician.
- Never invent patient history, test results, diagnoses, medications, allergies or other facts.
"""

_client = None


def _client_instance():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not configured. Add it to .env before using AI chat.")
        _client = genai.Client(api_key=key)
    return _client


def _memory_block(patient_memory: dict | None) -> str:
    if not patient_memory:
        return "Patient memory: none available."
    p = patient_memory.get("patient") or {}
    symptoms = patient_memory.get("symptoms") or []
    lines = [
        "Patient memory (reported information, not a diagnosis):",
        f"Name: {p.get('name') or 'not provided'}",
        f"Age: {p.get('age') if p.get('age') is not None else 'not provided'}",
        f"Sex: {p.get('sex') or 'not provided'}",
        f"Known conditions reported: {', '.join(p.get('conditions') or []) or 'none recorded'}",
        f"Allergies reported: {', '.join(p.get('allergies') or []) or 'none recorded'}",
        f"Medications reported: {', '.join(p.get('medications') or []) or 'none recorded'}",
        "Recurring/recent symptoms: " + (", ".join(
            s["symptom"] + (f" ({s['duration_text']})" if s.get("duration_text") else "")
            for s in symptoms
        ) or "none recorded"),
    ]
    return "\n".join(lines)


def _build_prompt(history: list[dict], user_message: str, patient_memory: dict | None = None) -> str:
    convo = [SYSTEM_PROMPT, "", _memory_block(patient_memory), ""]
    # Keep prompts bounded as a prototype grows.
    for turn in history[-20:]:
        speaker = "User" if turn["role"] == "user" else "Assistant"
        convo.append(f"{speaker}: {turn['content']}")
    convo.append(f"User: {user_message}")
    convo.append("Assistant:")
    return "\n".join(convo)


def ask_gemini(history: list[dict], user_message: str, patient_memory: dict | None = None) -> str:
    prompt = _build_prompt(history, user_message, patient_memory)
    interaction = _client_instance().interactions.create(model=MODEL_NAME, input=prompt)
    if interaction.steps:
        for step in interaction.steps:
            if step.type == "model_output" and step.content:
                for block in step.content:
                    if block.type == "text":
                        return block.text.strip()
    return "Sorry, I wasn't able to generate a response just now."


def stream_gemini_sync(history: list[dict], user_message: str, patient_memory: dict | None = None) -> Iterator[str]:
    prompt = _build_prompt(history, user_message, patient_memory)
    stream = _client_instance().interactions.create(model=MODEL_NAME, input=prompt, stream=True)
    for event in stream:
        if event.event_type == "step.delta" and event.delta.type == "text":
            yield event.delta.text


async def stream_gemini_async(history: list[dict], user_message: str, patient_memory: dict | None = None) -> AsyncIterator[str | dict[Any, Any]]:
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    def producer() -> None:
        try:
            for chunk in stream_gemini_sync(history, user_message, patient_memory):
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, {"error": str(exc)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    threading.Thread(target=producer, daemon=True).start()

    while True:
        item = await queue.get()
        if item is sentinel:
            break
        yield item
