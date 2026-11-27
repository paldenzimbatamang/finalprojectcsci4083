import config
from agents.audio_agent import make_voiceovers
from models import Stop, TripPlan


def test_make_voiceovers_in_stop_order_and_reuse(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", True)
    plan = TripPlan(
        trip_text="Mobile -> Biloxi",
        stops=[
            Stop(name="Mobile", narration="Welcome to Mobile."),
            Stop(name="Biloxi", narration="Next, explore the Biloxi waterfront."),
        ],
    )

    paths = make_voiceovers(plan, tmp_path)

    assert paths == [
        tmp_path / "audio" / "stop_1.mp3",
        tmp_path / "audio" / "stop_2.mp3",
    ]
    assert all(path.stat().st_size > 0 for path in paths)
    assert not list(tmp_path.rglob("*.partial.mp3"))

    original_times = [path.stat().st_mtime_ns for path in paths]
    assert make_voiceovers(plan, tmp_path) == paths
    assert [path.stat().st_mtime_ns for path in paths] == original_times