"""
text_agent.py - writes the trip description and a short narration for each stop.

Provider: Anthropic Claude (real mode is not built yet).

Input:  a TripPlan from the planner (stops have names, but no narration yet)
Output: the same TripPlan with plan.description filled in, and
        stop.narration filled in on every stop.

STATUS: mock mode only. Real mode (calling Claude) comes later.

The orchestrator only calls write_text().
"""

import config
from models import TripPlan


# ---------- Errors ----------

class TextAgentError(Exception):
    """A problem the person running the program should see, in plain English."""


# ---------- The function the orchestrator calls ----------

def write_text(plan: TripPlan) -> TripPlan:
    """
    Fill in the trip description and one narration per stop.

    Raises TextAgentError with a readable message if anything goes wrong.
    """
    # WHY check first: with no stops there is nothing to describe, and later
    # this check will stop us from paying for a useless Claude call.
    if not plan.stops:
        raise TextAgentError("The plan has no stops, so there is nothing to describe.")

    if config.MOCK_MODE:
        return _mock_text(plan)

    raise NotImplementedError(
        "The real text agent (calling Claude) isn't built yet. Run with MOCK_MODE=1."
    )


# ---------- Mock mode ----------

def _mock_text(plan: TripPlan) -> TripPlan:
    """
    Write fake text with no API call (free, works without an API key).
    """
    for number, stop in enumerate(plan.stops, start=1):
        narration = f"Stop {number}: welcome to {stop.name}, a great place to explore."

        # WHY cut it short: each clip is about 8 seconds, and about 20 words
        # fits in 8 seconds of speech. The real agent will follow the same rule.
        words = narration.split()
        stop.narration = " ".join(words[: config.NARRATION_MAX_WORDS])

    names = ", ".join(stop.name for stop in plan.stops)
    plan.description = f"[MOCK] This trip visits {len(plan.stops)} stops: {names}."
    return plan