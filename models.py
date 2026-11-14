"""
models.py - the shared data format for the whole pipeline.

WHY this file exists:
Every agent reads and writes the same TripPlan object. If we all agree on
its shape here, each teammate can build their agent separately and the
pieces will still fit together. Agents never talk to each other directly;
they only fill in fields on a TripPlan that the orchestrator hands them.

Who fills in what:
    Planner agent -> trip_text, stops (name, attractions, video_prompt)
    Text agent    -> description, and narration on each stop
    Human review  -> may edit any field before approving

This file deliberately has NO imports from our other files, so it can
never cause a circular-import problem.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# The professor didn't set this; we did, to keep video costs predictable.
# 5 stops = at most 5 paid video clips per run.
MAX_STOPS = 5


@dataclass
class Stop:
    """One place on the trip. Each stop becomes one video clip and one audio file."""

    name: str  # e.g. "Biloxi, MS"
    attractions: list[str] = field(default_factory=list)  # e.g. ["Biloxi Lighthouse"]
    video_prompt: str = ""  # what we ask Veo to film (silent drone shot)
    narration: str = ""  # what the voiceover says over this stop's clip


@dataclass
class TripPlan:
    """The whole trip. This object travels through every step of the pipeline."""

    trip_text: str  # exactly what the user typed
    stops: list[Stop] = field(default_factory=list)
    description: str = ""  # the written trip description (text agent)

    # ---------- Checking the plan ----------

    def problems(self, need_text: bool = False) -> list[str]:
        """
        Return a list of human-readable problems. An empty list means the plan is OK.

        WHY a list instead of raising an error: the human review step can show
        the reviewer EVERY problem at once after they edit the plan, instead of
        making them fix one, retry, fix the next, retry...

        need_text=False: check only what the planner should have produced.
        need_text=True:  also require the text agent's output (description +
                         narration). Use this before the video/audio steps.
        """
        found = []

        if not self.stops:
            found.append("The plan has no stops.")
        if len(self.stops) > MAX_STOPS:
            found.append(f"The plan has {len(self.stops)} stops; the limit is {MAX_STOPS}.")

        # enumerate(..., start=1) so messages say "Stop 1" like a person would.
        for number, stop in enumerate(self.stops, start=1):
            if not stop.name.strip():
                found.append(f"Stop {number} has no name.")
            if not stop.video_prompt.strip():
                found.append(f"Stop {number} ({stop.name}) has no video prompt.")
            if need_text and not stop.narration.strip():
                found.append(f"Stop {number} ({stop.name}) has no narration.")

        if need_text and not self.description.strip():
            found.append("The trip has no written description.")

        return found

    # ---------- Saving and loading as JSON ----------
    # WHY JSON: the reviewer can open plan.json in any text editor to make
    # changes, and we keep a record of exactly what was approved.

    def to_dict(self) -> dict:
        # asdict() turns the dataclass (and the Stops inside it) into plain dicts/lists.
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TripPlan":
        # Build Stop objects by hand, because json.load() gives us plain dicts.
        # .get(..., default) means a missing field doesn't crash the load;
        # problems() will report it instead.
        stops = [
            Stop(
                name=s.get("name", ""),
                attractions=list(s.get("attractions", [])),
                video_prompt=s.get("video_prompt", ""),
                narration=s.get("narration", ""),
            )
            for s in data.get("stops", [])
        ]
        return cls(
            trip_text=data.get("trip_text", ""),
            stops=stops,
            description=data.get("description", ""),
        )

    def save(self, path: Path) -> None:
        # indent=2 so the file is readable when a person opens it to edit.
        # ensure_ascii=False keeps characters like "é" readable instead of "é".
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "TripPlan":
        # This raises json.JSONDecodeError if the file isn't valid JSON (for example,
        # a reviewer left out a comma). The review step will catch that and explain it.
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
