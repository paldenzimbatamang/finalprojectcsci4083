"""
planner_agent.py - turns the user's trip text into a list of stops.

Provider: Anthropic Claude (real mode is not built yet).

Input:  "Mobile, AL -> Biloxi, MS -> New Orleans, LA"
Output: a TripPlan whose stops each have a name, attractions, and a
        video_prompt for Veo. Narration and description are left empty for
        the text agent.

STATUS: piece 1 of the planner. Input checks and mock mode work.
Real mode (calling Claude) raises NotImplementedError for now.

The orchestrator only calls plan_route().
"""

import config
from models import MAX_STOPS, Stop, TripPlan

# ---------- Settings ----------

# Trip text longer than this is almost certainly a mistake (or a pasted essay).
MAX_TRIP_TEXT_CHARS = 500

# Team decision: a single destination like "Lake Tahoe" becomes 3 stops.
SINGLE_DESTINATION_SPOTS = 3


# ---------- Errors ----------

class PlannerError(Exception):
    """A problem the person running the program should see, in plain English."""


# ---------- The function the orchestrator calls ----------

def plan_route(trip_text: str, feedback: str = "", previous_plan: TripPlan | None = None) -> TripPlan:
    """
    Turn trip text into a TripPlan with stops filled in.

    feedback and previous_plan are only used when the human reviewer chooses
    "regenerate". Mock mode uses feedback; previous_plan will be used by real
    mode in a later piece.

    Raises PlannerError with a readable message if anything goes wrong.
    """
    trip_text = trip_text.strip()

    # Check the input before doing any work (and, later, before spending money).
    if not trip_text:
        raise PlannerError('Please type a trip, e.g. "Lake Tahoe" or "Mobile, AL -> Biloxi, MS".')
    if len(trip_text) > MAX_TRIP_TEXT_CHARS:
        raise PlannerError(f"The trip text is too long ({len(trip_text)} characters; the limit is {MAX_TRIP_TEXT_CHARS}).")

    if config.MOCK_MODE:
        plan = _mock_plan(trip_text, feedback)
        _check_stop_count(plan)
        return plan

    raise NotImplementedError(
        "The real planner (calling Claude) isn't built yet. Run with --mock to use the mock planner."
    )


# ---------- Mock mode ----------

def _mock_plan(trip_text: str, feedback: str) -> TripPlan:
    """
    Build a fake plan with no API call (free, works without an API key).

    "A -> B -> C" gives 3 stops in order, and a single destination gives
    3 spots, the same rule the real planner will follow. Feedback is added
    to each prompt so you can SEE that "regenerate" really changed the plan.
    """
    names = [part.strip() for part in trip_text.split("->") if part.strip()]
    if len(names) == 1:
        names = [f"{names[0]} (spot {n})" for n in range(1, SINGLE_DESTINATION_SPOTS + 1)]

    stops = []
    for name in names:
        prompt = f"[MOCK] Slow aerial drone shot over {name} on a clear afternoon."
        if feedback:
            prompt += f" (Reviewer feedback: {feedback})"
        stops.append(Stop(
            name=name,
            attractions=[f"Mock attraction 1 near {name}", f"Mock attraction 2 near {name}"],
            video_prompt=prompt,
        ))
    return TripPlan(trip_text=trip_text, stops=stops)


def _check_stop_count(plan: TripPlan) -> None:
    """
    Stop with a clear message if the plan has no stops or too many.

    These are problems with the TRIP TEXT, so the person needs to change
    what they typed.
    """
    if not plan.stops:
        raise PlannerError(
            "Couldn't find any places in your trip. "
            'Try something like "Lake Tahoe" or "Mobile, AL -> Biloxi, MS".'
        )
    if len(plan.stops) > MAX_STOPS:
        raise PlannerError(
            f"Trips are limited to {MAX_STOPS} stops, but this one has {len(plan.stops)}. "
            "Please shorten the trip and try again."
        )
