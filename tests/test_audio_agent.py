import subprocess

import pytest
from agents import audio_agent
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

    # Decode the actual MP3s; nonempty bytes alone do not prove they are playable.
    for path in paths:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
            check=True, capture_output=True,
        )


def test_real_mode_reads_key_from_elevenlabs_api_key_setting(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="^ELEVENLABS_API_KEY is not set"):
        audio_agent._speech_client()


def test_standalone_mock_forces_offline_mode(tmp_path, monkeypatch):
    from mock_audio import main

    monkeypatch.setattr(config, "MOCK_MODE", False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    def forbidden_client():
        pytest.fail("Mock runner must never create an API client")

    monkeypatch.setattr(audio_agent, "_speech_client", forbidden_client)
    assert main(["--output-dir", str(tmp_path), "--narration", "Hello from Mobile."]) == 0
    path = tmp_path / "audio" / "stop_1.mp3"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
        check=True, capture_output=True,
    )
    assert config.MOCK_MODE is False
