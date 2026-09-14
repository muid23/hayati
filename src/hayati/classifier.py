"""
Safety & triage classifier.

This is a DEMO ruleset only -- simple keyword matching, not a clinically
validated triage tool. In the real architecture (see Architecture.md),
this component must be authored and signed off by a licensed clinician,
and tested far more rigorously than substring matching.

The point this prototype demonstrates is structural, not clinical:
this function runs BEFORE the LLM is ever called, and its decision
cannot be overridden by the model.
"""

RED_FLAGS = {
    "chest_pain": ["chest pain", "tightness in my chest", "pressure in my chest"],
    "breathing": ["can't breathe", "cant breathe", "difficulty breathing", "shortness of breath"],
    "stroke_signs": ["face drooping", "slurred speech", "sudden numbness", "sudden confusion"],
    "severe_bleeding": ["severe bleeding", "won't stop bleeding", "wont stop bleeding"],
    "consciousness": ["passed out", "lost consciousness", "unresponsive"],
    "anaphylaxis": ["throat closing", "swelling of my throat", "severe allergic reaction"],
    "suicidal_ideation": ["want to end my life", "kill myself", "suicidal"],
}


def classify(message: str) -> dict:
    """
    Returns {"level": "emergency" | "routine", "matched": [flag_names]}

    Deliberately simple and deterministic: no LLM call, no randomness.
    Every input either matches a rule or it doesn't -- that determinism
    is what makes this component auditable.
    """
    text = message.lower()
    matched = []

    for flag_name, phrases in RED_FLAGS.items():
        if any(phrase in text for phrase in phrases):
            matched.append(flag_name)

    level = "emergency" if matched else "routine"
    return {"level": level, "matched": matched}
