"""
Thin wrapper around the Gemini API.

Only called for messages the safety classifier has already cleared as
non-emergency -- this module has no visibility into, and no ability to
override, the triage decision.

Model IDs on the Gemini API change over time. If the model below stops
resolving, check https://ai.google.dev/gemini-api/docs/models for the
current free-tier Flash model ID and swap it in.
"""

import asyncio
import os
import threading
from collections.abc import AsyncIterator, Iterator
from typing import Any

from google import genai

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """You are a general health information assistant, NOT a doctor.
Rules you must always follow:
- Never provide a diagnosis. Describe possibilities in general, educational terms only.
- Always recommend the user consult a licensed clinician for any real concern.
- Keep responses short (3-5 sentences) and in plain language.
- If the user describes something that sounds serious, say so plainly and
  recommend they seek in-person care, even though you are not the emergency
  detection layer.
- Never claim certainty about what a symptom means.
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


def _build_prompt(history: list[dict], user_message: str) -> str:
    convo = [SYSTEM_PROMPT, ""]
    for turn in history:
        speaker = "User" if turn["role"] == "user" else "Assistant"
        convo.append(f"{speaker}: {turn['content']}")
    convo.append(f"User: {user_message}")
    convo.append("Assistant:")
    return "\n".join(convo)


def ask_gemini(history: list[dict], user_message: str) -> str:
    """Non-streaming call -- used by the plain HTTP /chat endpoint."""
    prompt = _build_prompt(history, user_message)
    interaction = _client_instance().interactions.create(model=MODEL_NAME, input=prompt)
    if interaction.steps:
        for step in interaction.steps:
            if step.type == "model_output":
                if step.content:
                    for block in step.content:
                        if block.type == "text":
                            return block.text.strip()
    return "Sorry, I wasn't able to generate a response just now."


def stream_gemini_sync(history: list[dict], user_message: str) -> Iterator[str]:
    """
    Synchronous generator yielding text chunks as they arrive.
    Blocking -- must be run off the asyncio event loop thread
    (see stream_gemini_async below).
    """
    prompt = _build_prompt(history, user_message)
    stream = _client_instance().interactions.create(model=MODEL_NAME, input=prompt, stream=True)
    for event in stream:
        if event.event_type == "step.delta" and event.delta.type == "text":
            yield event.delta.text


async def stream_gemini_async(
    history: list[dict], user_message: str
) -> AsyncIterator[str | dict[Any, Any]]:
    """
    Bridges the blocking Gemini stream into the asyncio world so it can be
    awaited chunk-by-chunk inside an async websocket handler without
    blocking the event loop. Runs the blocking generator in a background
    thread and forwards each chunk into an asyncio.Queue.
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    SENTINEL = object()

    def producer() -> None:
        try:
            for chunk in stream_gemini_sync(history, user_message):
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as exc:  # surfaced to the caller as a dict
            loop.call_soon_threadsafe(queue.put_nowait, {"error": str(exc)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)

    threading.Thread(target=producer, daemon=True).start()

    while True:
        item = await queue.get()
        if item is SENTINEL:
            break
        yield item
