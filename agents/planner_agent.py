"""
planner_agent.py - turns the user's trip text into a list of stops.

Provider: Anthropic Claude (model set by PLANNER_MODEL in .env; default claude-sonnet-5-5).

Input:  "Mobile, AL -> Biloxi, MS -> New Orleans, LA"
Output: a TripPlan whose stops each have a name, 2-4 attractions, and a
        video_prompt for Veo. Narration and description are left empty for
        the text agent.

The orchestrator only calls plan_route(). Everything else in this file is a
helper for it.
"""

import json

import anthropic

import config
from models import MAX_STOPS, Stop, TripPlan

# ---------- Settings ----------

# Effort controls how much Claude thinks before answering. Anthropic's docs
# suggest "low" as the starting point for Sonnet 5.5 on content-generation
# tasks like this one: it skips thinking on simple requests, so it's cheapest.
# (We don't send a "thinking" setting at all: on Sonnet 5.5 the default is
# adaptive thinking, and trying to turn it off with "disabled" is an error.)
PLANNER_EFFORT = "low"

# Room for Claude's answer. A 5-stop plan is well under 1,000 tokens; the
# extra space means a long answer is never cut off halfway.
MAX_TOKENS = 16000

# Trip text longer than this is almost certainly a mistake (or a pasted essay).
MAX_TRIP_TEXT_CHARS = 500

# Team decision: a single destination like "Lake Tahoe" becomes 3 stops.
SINGLE_DESTINATION_SPOTS = 3


# ---------- The instructions we send to Claude ----------
# WHY a system prompt: these rules are the same for every trip, so they go in
# the "system" field. Only the trip itself goes in the user message.

SYSTEM_PROMPT = f"""You plan short trips for a tool that makes silent drone-style video previews.

Turn the user's trip into a list of stops.

Choosing stops:
- If the user lists places, use exactly those places, in the user's order. Do not add or remove any.
- If the user lists more than {MAX_STOPS} places, still return ALL of them. The program will ask the user to shorten the trip.
- If the user gives one destination (for example "Lake Tahoe"), choose {SINGLE_DESTINATION_SPOTS} scenic, well-known spots in or right around it, and make each spot a stop.
- If the text does not name any real place, return an empty list of stops.
- Write each stop's name the way a traveler would say it, e.g. "Biloxi, MS" or "Emerald Bay State Park".

For each stop:
- attractions: 2 to 4 real, well-known attractions at or near that stop.
- video_prompt: one or two sentences describing a single 8-second aerial drone shot of the stop for an AI video generator. Describe the camera movement, the landscape or skyline, the time of day, and the weather. Show only scenery that really exists there. Do not include close-ups of people, readable text, signs, or logos. Do not mention sound, music, or narration: the video is silent."""


# The exact shape Claude's answer must have. "Structured outputs" makes the
# API enforce this, so we get valid JSON back instead of hoping for it.
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "stops": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "attractions": {"type": "array", "items": {"type": "string"}},
                    "video_prompt": {"type": "string"},
                },
                "required": ["name", "attractions", "video_prompt"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["stops"],
    "additionalProperties": False,
}


# ---------- Errors ----------

class PlannerError(Exception):
    """A problem the person running the program should see, in plain English."""


class _BadReply(Exception):
    """Claude's answer couldn't be read. Used inside this file to trigger one retry."""


# ---------- The function the orchestrator calls ----------

def plan_route(trip_text: str, feedback: str = "", previous_plan: TripPlan | None = None) -> TripPlan:
    """
    Turn trip text into a TripPlan with stops filled in.

    feedback and previous_plan are only used when the human reviewer chooses
    "regenerate": Claude sees its last plan plus the reviewer's note, so it
    adjusts that plan instead of starting from scratch.

    Raises PlannerError with a readable message if anything goes wrong.
    """
    trip_text = trip_text.strip()

    # Check the input before spending money on an API call.
    if not trip_text:
        raise PlannerError('Please type a trip, e.g. "Lake Tahoe" or "Mobile, AL -> Biloxi, MS".')
    if len(trip_text) > MAX_TRIP_TEXT_CHARS:
        raise PlannerError(f"The trip text is too long ({len(trip_text)} characters; the limit is {MAX_TRIP_TEXT_CHARS}).")

    if config.MOCK_MODE:
        plan = _mock_plan(trip_text, feedback)
        _check_stop_count(plan)
        return plan

    return _plan_with_claude(trip_text, feedback, previous_plan)


# ---------- Mock mode ----------

def _mock_plan(trip_text: str, feedback: str) -> TripPlan:
    """
    Build a fake plan with no API call (free, works without an API key).

    It copies what the real planner does closely enough to test everything
    downstream: "A -> B -> C" gives 3 stops in order, and a single destination
    gives 3 spots. Feedback is added to each prompt so you can SEE that
    "regenerate" really changed the plan.
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


# ---------- Real mode ----------

def _plan_with_claude(trip_text: str, feedback: str, previous_plan: TripPlan | None) -> TripPlan:
    """
    Ask Claude for a plan, check it, and retry ONCE if the answer was unusable.

    WHY only one retry: if Claude gets it wrong twice in a row, a third try
    probably won't help, and each try costs money. Better to stop and tell
    the person what went wrong.
    """
    # max_retries=3: the SDK automatically retries network errors, rate limits
    # (429) and server errors (5xx), waiting a bit longer each time.
    client = anthropic.Anthropic(api_key=config.get_api_key("ANTHROPIC_API_KEY"), max_retries=3)
    user_message = _build_user_message(trip_text, feedback, previous_plan)

    message = user_message
    problems: list[str] = []
    for _attempt in range(2):  # first try + one retry
        try:
            data = _ask_claude(client, message)
        except _BadReply as reason:
            problems = [str(reason)]
        else:
            plan = _plan_from_reply(data, trip_text)
            _check_stop_count(plan)  # 0 or more than 5 stops: tell the user, don't retry
            problems = plan.problems()
            if not problems:
                return plan

        # Retry with the original request plus a list of what was wrong.
        message = user_message + "\n\nYour previous answer had these problems. Fix them:\n" + "\n".join(
            f"- {p}" for p in problems
        )

    raise PlannerError("Claude's plan still had problems after a retry:\n" + "\n".join(f"- {p}" for p in problems))


def _build_user_message(trip_text: str, feedback: str, previous_plan: TripPlan | None) -> str:
    """The user message: just the trip, plus the old plan and feedback when regenerating."""
    message = f"Trip: {trip_text}"
    if previous_plan is not None and feedback:
        # Only the planner's own fields; narration belongs to the text agent.
        old_stops = [
            {"name": s.name, "attractions": s.attractions, "video_prompt": s.video_prompt}
            for s in previous_plan.stops
        ]
        message += (
            "\n\nHere is the plan you made before:\n"
            + json.dumps({"stops": old_stops}, indent=2, ensure_ascii=False)
            + f"\n\nA human reviewer asked for these changes: {feedback}\n"
            "Make a new plan with those changes. Keep everything else the same unless the feedback says otherwise."
        )
    elif feedback:
        message += f"\n\nA human reviewer asked for these changes: {feedback}"
    return message


def _ask_claude(client: anthropic.Anthropic, message: str) -> dict:
    """
    Send one request to Claude and return its answer as a dict.

    Raises PlannerError for problems a retry can't fix (bad key, refusal...),
    and _BadReply when the answer arrived but couldn't be read (worth one retry).
    """
    # Catch the most specific errors first. Each gets its own message, because
    # "your API key is wrong" and "you're offline" need different fixes.
    try:
        response = client.messages.create(
            model=config.PLANNER_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
            output_config={
                "effort": PLANNER_EFFORT,
                "format": {"type": "json_schema", "schema": PLAN_SCHEMA},
            },
        )
    except anthropic.AuthenticationError:
        raise PlannerError("Claude rejected the API key. Check ANTHROPIC_API_KEY in .env.") from None
    except anthropic.NotFoundError:
        raise PlannerError(f"Claude model '{config.PLANNER_MODEL}' was not found. Check PLANNER_MODEL in .env.") from None
    except anthropic.BadRequestError as error:
        raise PlannerError(f"Claude rejected the request: {error.message}") from None
    except anthropic.RateLimitError:
        raise PlannerError("Claude is rate-limiting us, even after retrying. Wait a minute and try again.") from None
    except anthropic.APIStatusError as error:
        raise PlannerError(f"Claude's servers returned an error ({error.status_code}). Try again later.") from None
    except anthropic.APIConnectionError:
        raise PlannerError("Couldn't reach Claude. Check your internet connection and try again.") from None

    # stop_reason says WHY Claude stopped writing. Check it before reading the answer.
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        explanation = getattr(details, "explanation", None) or "no reason given"
        raise PlannerError(f"Claude declined to plan this trip ({explanation}).")
    if response.stop_reason == "max_tokens":
        raise PlannerError("Claude's answer was cut off because it was too long. Try a shorter trip.")

    # The answer can contain several "blocks" (for example an empty thinking
    # block first), so look for the text block by type, not by position.
    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise _BadReply("The answer contained no text.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise _BadReply("The answer was not valid JSON.") from None
    if not isinstance(data, dict):
        raise _BadReply("The answer was not a JSON object.")
    return data


def _plan_from_reply(data: dict, trip_text: str) -> TripPlan:
    """
    Turn Claude's JSON into a TripPlan.

    TripPlan.from_dict() fills in anything missing with empty values instead of
    crashing; plan.problems() then reports what's missing so we can retry.
    Kept separate from the API call so tests can feed it fake answers for free.
    """
    stops = data.get("stops")
    if not isinstance(stops, list):
        stops = []
    # Ignore anything in the list that isn't a stop object.
    stops = [s for s in stops if isinstance(s, dict)]
    return TripPlan.from_dict({"trip_text": trip_text, "stops": stops})


def _check_stop_count(plan: TripPlan) -> None:
    """
    Stop with a clear message if the plan has no stops or too many.

    These are problems with the TRIP TEXT, not with Claude's answer, so
    retrying wouldn't help. The person needs to change what they typed.
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
