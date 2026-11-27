"""
human_review.py - the human-in-the-loop checkpoint (professor's requirement #3).

WHY this step exists: video is the slowest and most expensive step. A person
checks the plan BEFORE any money is spent on video or voice.

The person can choose:
    a = approve     -> go on to video and audio
    e = edit        -> change plan.json in any text editor, then we reload it
    r = regenerate  -> ask the planner for a new plan, with feedback
    q = quit        -> stop here, nothing gets paid for

This file does NOT call the planner itself. It only tells the orchestrator
what the person chose. (Agents and steps never call each other.)

The orchestrator only calls review_plan().
"""

import json
from dataclasses import dataclass
from pathlib import Path

from models import TripPlan


@dataclass
class ReviewResult:
    """What the person decided. The orchestrator reads this and acts on it."""

    action: str  # "approve", "regenerate", or "quit"
    plan: TripPlan  # the plan, possibly edited by the person
    feedback: str = ""  # only used for "regenerate"


def review_plan(plan: TripPlan, plan_path: Path, ask=input) -> ReviewResult:
    """
    Show the plan and let the person decide what to do with it.

    plan_path: where plan.json is saved, so the person can open and edit it.
    ask: the function that reads the person's answer. Normally this is
         Python's input(). Tests pass a fake one so nobody has to type.
    """
    # Save first, so there is always a copy of exactly what was reviewed.
    plan.save(plan_path)

    # WHY a loop: after an edit or a typo we show the plan again and ask again,
    # until the person approves, regenerates, or quits.
    while True:
        _show_plan(plan)
        choice = ask("\n[a]pprove, [e]dit, [r]egenerate, or [q]uit? ").strip().lower()

        if choice == "a":
            # Don't let an incomplete plan through: missing pieces would make
            # the video or audio step fail AFTER we've started paying.
            problems = plan.problems(need_text=True)
            if problems:
                print("\nCan't approve yet. Please fix these first:")
                for problem in problems:
                    print(f"  - {problem}")
                continue
            plan.save(plan_path)  # keep a record of exactly what was approved
            return ReviewResult(action="approve", plan=plan)

        if choice == "e":
            print(f"\nOpen this file in any editor, make your changes, and save it:\n  {plan_path}")
            ask("Press Enter when you're done editing... ")
            try:
                plan = TripPlan.load(plan_path)
            except json.JSONDecodeError as error:
                # A missing comma or quote is the usual cause. Keep the old plan.
                print(f"\nplan.json has a typo near line {error.lineno} "
                      "(maybe a missing comma or quote). Fix it and choose [e] again.")
            continue

        if choice == "r":
            feedback = ask("What should change? (for example: 'show sunset shots'): ").strip()
            return ReviewResult(action="regenerate", plan=plan, feedback=feedback)

        if choice == "q":
            return ReviewResult(action="quit", plan=plan)

        print("Please type a, e, r, or q.")


def _show_plan(plan: TripPlan) -> None:
    """Print the plan in a way that's easy for a person to read."""
    print("\n" + "=" * 60)
    print(f"TRIP: {plan.trip_text}")
    print(f"DESCRIPTION: {plan.description}")
    for number, stop in enumerate(plan.stops, start=1):
        print(f"\nStop {number}: {stop.name}")
        print(f"  Attractions:  {', '.join(stop.attractions)}")
        print(f"  Video prompt: {stop.video_prompt}")
        print(f"  Narration:    {stop.narration}")
    print("=" * 60)