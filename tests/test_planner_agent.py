"""
Tests for agents/planner_agent.py.

None of these call the real Claude API, so they're free and work offline.
  - Mock mode tests check the fake planner the rest of the pipeline uses.
  - Real-mode tests replace the API call with a fake one, so we can check
    our own logic: retries, error messages, and reading Claude's answer.

Run with:  pytest tests/test_planner_agent.py
"""

import json
from types import SimpleNamespace

import pytest

import config
from agents import planner_agent
from agents.planner_agent import PlannerError, plan_route
from models import Stop, TripPlan


# ---------- Shared setup ----------

@pytest.fixture
def mock_mode(monkeypatch):
    """Turn mock mode on for one test (monkeypatch undoes it afterwards)."""
    monkeypatch.setattr(config, "MOCK_MODE", True)


@pytest.fixture
def real_mode(monkeypatch):
    """Turn mock mode off and give a fake API key. No real request is ever sent."""
    monkeypatch.setattr(config, "MOCK_MODE", False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")


def good_stop(name="Biloxi, MS"):
    return {"name": name, "attractions": ["Biloxi Lighthouse"], "video_prompt": "Drone shot over the coast."}


def fake_reply_sequence(monkeypatch, replies):
    """
    Replace _ask_claude with a fake that returns each item of `replies` in turn
    (or raises it, if it's an exception). Returns a list that records every
    message "sent", so tests can count calls and check the retry text.
    """
    sent = []
    queue = list(replies)

    def fake_ask(_client, message):
        sent.append(message)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(planner_agent, "_ask_claude", fake_ask)
    return sent


# ---------- Input checks (both modes) ----------

def test_empty_trip_is_rejected(mock_mode):
    with pytest.raises(PlannerError, match="Please type a trip"):
        plan_route("   ")


def test_very_long_trip_is_rejected(mock_mode):
    with pytest.raises(PlannerError, match="too long"):
        plan_route("x" * 501)


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


def test_mock_feedback_shows_up_in_prompts(mock_mode):
    plan = plan_route("A -> B", feedback="more sunsets")
    assert all("more sunsets" in s.video_prompt for s in plan.stops)


def test_mock_mode_never_creates_an_api_client(mock_mode, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("mock mode must not create an Anthropic client")

    monkeypatch.setattr(planner_agent.anthropic, "Anthropic", explode)
    plan_route("A -> B")  # would raise if a client were created


# ---------- Reading Claude's answer ----------

def test_plan_from_good_reply():
    plan = planner_agent._plan_from_reply({"stops": [good_stop("A"), good_stop("B")]}, "A -> B")
    assert [s.name for s in plan.stops] == ["A", "B"]
    assert plan.problems() == []


def test_plan_from_reply_with_missing_fields_reports_problems():
    plan = planner_agent._plan_from_reply({"stops": [{"name": "A"}]}, "A")
    assert any("no video prompt" in p for p in plan.problems())


def test_plan_from_reply_ignores_junk():
    plan = planner_agent._plan_from_reply({"stops": ["not a stop", good_stop("A")]}, "A")
    assert [s.name for s in plan.stops] == ["A"]
    assert planner_agent._plan_from_reply({"stops": "oops"}, "A").stops == []


# ---------- Real mode: retries and errors (API call faked) ----------

def test_real_mode_good_first_answer_means_one_call(real_mode, monkeypatch):
    sent = fake_reply_sequence(monkeypatch, [{"stops": [good_stop()]}])
    plan = plan_route("Biloxi, MS")
    assert len(sent) == 1
    assert plan.stops[0].name == "Biloxi, MS"


def test_real_mode_bad_answer_is_retried_once_with_the_problems(real_mode, monkeypatch):
    bad = {"stops": [{"name": "Biloxi, MS", "attractions": [], "video_prompt": ""}]}
    sent = fake_reply_sequence(monkeypatch, [bad, {"stops": [good_stop()]}])
    plan = plan_route("Biloxi, MS")
    assert len(sent) == 2
    assert "no video prompt" in sent[1]  # the retry tells Claude what was wrong
    assert plan.problems() == []


def test_real_mode_unreadable_answer_is_retried_once(real_mode, monkeypatch):
    sent = fake_reply_sequence(monkeypatch, [planner_agent._BadReply("not JSON"), {"stops": [good_stop()]}])
    plan_route("Biloxi, MS")
    assert len(sent) == 2


def test_real_mode_two_bad_answers_give_up(real_mode, monkeypatch):
    bad = {"stops": [{"name": "A", "attractions": [], "video_prompt": ""}]}
    sent = fake_reply_sequence(monkeypatch, [bad, bad])
    with pytest.raises(PlannerError, match="still had problems"):
        plan_route("A")
    assert len(sent) == 2  # never a third try


def test_real_mode_too_many_stops_is_not_retried(real_mode, monkeypatch):
    six = {"stops": [good_stop(str(n)) for n in range(6)]}
    sent = fake_reply_sequence(monkeypatch, [six])
    with pytest.raises(PlannerError, match="limited to 5 stops"):
        plan_route("1 -> 2 -> 3 -> 4 -> 5 -> 6")
    assert len(sent) == 1


def test_real_mode_no_places_found(real_mode, monkeypatch):
    fake_reply_sequence(monkeypatch, [{"stops": []}])
    with pytest.raises(PlannerError, match="Couldn't find any places"):
        plan_route("asdfgh")


def test_regenerate_sends_previous_plan_and_feedback(real_mode, monkeypatch):
    sent = fake_reply_sequence(monkeypatch, [{"stops": [good_stop("Gulf Shores, AL")]}])
    old = TripPlan("Biloxi, MS", [Stop("Biloxi, MS", ["Lighthouse"], "Old prompt", narration="secret")])
    plan_route("Biloxi, MS", feedback="swap Biloxi for Gulf Shores", previous_plan=old)
    assert "swap Biloxi for Gulf Shores" in sent[0]
    assert "Old prompt" in sent[0]
    assert "secret" not in sent[0]  # narration belongs to the text agent, not sent here


# ---------- Real mode: one API response (client faked) ----------

def fake_client(response):
    """An object shaped like anthropic.Anthropic whose messages.create() returns `response`."""
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


def fake_response(stop_reason="end_turn", text=None, stop_details=None):
    blocks = [SimpleNamespace(type="thinking", thinking="")]  # an empty thinking block first, like the real API
    if text is not None:
        blocks.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(stop_reason=stop_reason, content=blocks, stop_details=stop_details)


def test_ask_claude_reads_text_block_after_thinking_block():
    reply = fake_response(text=json.dumps({"stops": [good_stop()]}))
    assert planner_agent._ask_claude(fake_client(reply), "Trip: Biloxi")["stops"][0]["name"] == "Biloxi, MS"


def test_ask_claude_refusal_is_an_error():
    reply = fake_response(stop_reason="refusal", stop_details=SimpleNamespace(explanation="policy"))
    with pytest.raises(PlannerError, match="declined.*policy"):
        planner_agent._ask_claude(fake_client(reply), "Trip: x")


def test_ask_claude_cut_off_answer_is_an_error():
    with pytest.raises(PlannerError, match="cut off"):
        planner_agent._ask_claude(fake_client(fake_response(stop_reason="max_tokens", text='{"stops": [')), "x")


def test_ask_claude_invalid_json_is_a_bad_reply():
    with pytest.raises(planner_agent._BadReply):
        planner_agent._ask_claude(fake_client(fake_response(text="not json")), "x")


def test_ask_claude_sends_the_right_settings():
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return fake_response(text='{"stops": []}')

    planner_agent._ask_claude(SimpleNamespace(messages=SimpleNamespace(create=create)), "Trip: x")
    assert captured["model"] == config.PLANNER_MODEL
    assert captured["output_config"]["effort"] == "low"
    assert captured["output_config"]["format"]["type"] == "json_schema"
    assert "thinking" not in captured  # Sonnet 5.5: leave thinking at its adaptive default
