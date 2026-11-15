"""
Tests for agents/planner_agent.py, piece 1: input checks and mock mode.

None of these call the real Claude API, so they're free and work offline.

Run with:  pytest tests/test_planner_agent.py
"""

import pytest

import config
from agents.planner_agent import PlannerError, plan_route


# ---------- Shared setup ----------

@pytest.fixture
def mock_mode(monkeypatch):
    """Turn mock mode on for one test (monkeypatch undoes it afterwards)."""
    monkeypatch.setattr(config, "MOCK_MODE", True)


@pytest.fixture
def real_mode(monkeypatch):
    """Turn mock mode off for one test."""
    monkeypatch.setattr(config, "MOCK_MODE", False)


# ---------- Input checks ----------

def test_empty_trip_is_rejected(mock_mode):
    with pytest.raises(PlannerError, match="Please type a trip"):
        plan_route("   ")


def test_very_long_trip_is_rejected(mock_mode):
    with pytest.raises(PlannerError, match="too long"):
        plan_route("x" * 501)


def test_input_is_checked_in_real_mode_too(real_mode):
    # The input check happens before the "not built yet" error.
    with pytest.raises(PlannerError, match="Please type a trip"):
        plan_route("")


# ---------- Mock mode ----------

def test_mock_route_keeps_stops_in_order(mock_mode):
    plan = plan_route("Mobile, AL -> Biloxi, MS -> New Orleans, LA")
    assert [s.name for s in plan.stops] == ["Mobile, AL", "Biloxi, MS", "New Orleans, LA"]
    assert plan.trip_text == "Mobile, AL -> Biloxi, MS -> New Orleans, LA"


def test_mock_single_destination_gives_three_spots(mock_mode):
    plan = plan_route("Lake Tahoe")
    assert len(plan.stops) == 3
    assert all(s.name.startswith("Lake Tahoe") for s in plan.stops)


def test_mock_plan_passes_the_planner_checks(mock_mode):
    plan = plan_route("A -> B")
    assert plan.problems() == []
    # The text agent's fields are left empty for the text agent.
    assert plan.description == ""
    assert all(s.narration == "" for s in plan.stops)


def test_mock_more_than_five_places_is_an_error(mock_mode):
    with pytest.raises(PlannerError, match="limited to 5 stops, but this one has 6"):
        plan_route("A -> B -> C -> D -> E -> F")


def test_mock_no_places_is_an_error(mock_mode):
    with pytest.raises(PlannerError, match="Couldn't find any places"):
        plan_route("->")


def test_mock_feedback_shows_up_in_prompts(mock_mode):
    plan = plan_route("A -> B", feedback="more sunsets")
    assert all("more sunsets" in s.video_prompt for s in plan.stops)


# ---------- Real mode (not built yet) ----------

def test_real_mode_is_not_built_yet(real_mode):
    with pytest.raises(NotImplementedError, match="isn't built yet"):
        plan_route("Lake Tahoe")
