"""Transparent prototype condition-risk and outbreak-risk analytics.

This module deliberately does NOT diagnose disease. It provides an explainable
ranking of possible condition categories from reported symptoms and a simple
surveillance signal based on aggregated reports. Both outputs require clinical
or epidemiological review before real-world decisions.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import re

CONDITION_PROFILES = {
    "malaria-like illness": {
        "symptoms": {"fever": 3, "headache": 2, "chills": 3, "body aches": 2, "fatigue": 1, "sweating": 2},
        "note": "Symptoms can occur with malaria and other febrile illnesses; testing is needed to confirm the cause.",
    },
    "influenza-like respiratory infection": {
        "symptoms": {"fever": 2, "cough": 3, "sore throat": 2, "headache": 1, "body aches": 2, "fatigue": 1},
        "note": "This pattern can occur with influenza and other respiratory infections; symptoms alone cannot confirm the cause.",
    },
    "gastrointestinal infection": {
        "symptoms": {"diarrhea": 3, "vomiting": 3, "stomach pain": 2, "abdominal pain": 2, "fever": 1, "nausea": 2},
        "note": "Several infections and non-infectious conditions can cause this pattern; hydration and professional assessment may be appropriate.",
    },
    "dengue-like febrile illness": {
        "symptoms": {"fever": 3, "headache": 2, "body aches": 3, "joint pain": 2, "rash": 2, "nausea": 1},
        "note": "This pattern can occur with dengue and other febrile illnesses; laboratory assessment is required for confirmation.",
    },
}

SYMPTOM_ALIASES = {
    "high temperature": "fever", "temperature": "fever", "hot": "fever",
    "coughing": "cough", "throat pain": "sore throat", "sore throat": "sore throat",
    "head pain": "headache", "loose stool": "diarrhea", "loose stools": "diarrhea",
    "stomach ache": "stomach pain", "tummy pain": "stomach pain", "abdominal pain": "abdominal pain",
    "joint aches": "joint pain", "muscle aches": "body aches", "body pain": "body aches",
}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("’", "'"))


def extract_symptoms(text: str) -> list[str]:
    value = _normalise(text)
    found: list[str] = []
    terms = set(SYMPTOM_ALIASES) | {s for p in CONDITION_PROFILES.values() for s in p["symptoms"]}
    for term in sorted(terms, key=len, reverse=True):
        if term in value:
            canonical = SYMPTOM_ALIASES.get(term, term)
            if canonical not in found:
                found.append(canonical)
    return found


def assess_possible_conditions(text: str) -> dict:
    symptoms = extract_symptoms(text)
    scored = []
    for name, profile in CONDITION_PROFILES.items():
        score = sum(weight for symptom, weight in profile["symptoms"].items() if symptom in symptoms)
        matched = [s for s in profile["symptoms"] if s in symptoms]
        if score:
            max_score = sum(profile["symptoms"].values())
            percentage = round(min(100, (score / max_score) * 100))
            scored.append({"condition": name, "score": percentage, "matched_symptoms": matched, "note": profile["note"]})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {
        "type": "possible_condition_assessment",
        "symptoms_detected": symptoms,
        "results": scored[:3],
        "disclaimer": "This is an educational risk assessment, not a diagnosis. Symptoms overlap across many conditions; a qualified clinician and appropriate testing are required for diagnosis.",
    }


def outbreak_risk(reports: list[dict], window_days: int = 7) -> dict:
    """Calculate a simple surveillance signal from structured reports.

    Signal components: recent volume, growth versus the preceding window,
    geographic clustering, and severe-report proportion. This is a prototype
    screening signal, not a pandemic prediction model.
    """
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=window_days)
    previous_cutoff = recent_cutoff - timedelta(days=window_days)
    recent = []
    previous = []
    for report in reports:
        try:
            dt = datetime.fromisoformat(report["timestamp"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if dt >= recent_cutoff:
            recent.append(report)
        elif dt >= previous_cutoff:
            previous.append(report)

    recent_n = len(recent)
    previous_n = len(previous)
    growth = round(((recent_n - previous_n) / max(previous_n, 1)) * 100, 1)
    locations = Counter((r.get("location") or "unknown").strip().lower() for r in recent)
    conditions = Counter((r.get("condition") or "unspecified").strip().lower() for r in recent)
    severe = sum(1 for r in recent if r.get("severity") in {"high", "severe", "emergency"})
    severe_pct = round((severe / recent_n) * 100, 1) if recent_n else 0

    score = 0
    if recent_n >= 10: score += 25
    elif recent_n >= 5: score += 15
    if growth >= 100: score += 30
    elif growth >= 50: score += 20
    elif growth > 0: score += 10
    if len(locations) >= 3: score += 20
    elif len(locations) == 2: score += 10
    if severe_pct >= 30: score += 25
    elif severe_pct >= 15: score += 15

    level = "high" if score >= 60 else "elevated" if score >= 30 else "low"
    return {
        "type": "surveillance_risk_signal",
        "risk_level": level,
        "risk_score": score,
        "recent_reports": recent_n,
        "previous_reports": previous_n,
        "growth_percent": growth,
        "locations_with_reports": dict(locations),
        "condition_counts": dict(conditions),
        "severe_report_percent": severe_pct,
        "window_days": window_days,
        "interpretation": "This is a screening signal for unusual reporting activity, not a prediction of a pandemic. Public-health/epidemiological investigation is required before any outbreak conclusion or alert.",
    }
