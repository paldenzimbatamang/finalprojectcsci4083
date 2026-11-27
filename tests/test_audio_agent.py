"""
Tests for agents/audio_agent.py.

None of these call the real ElevenLabs API, so they're free and work offline.

Run with:  pytest tests/test_audio_agent.py
"""

import pytest

from agents import audio_agent


def test_real_mode_reads_key_from_elevenlabs_api_key_setting(monkeypatch):
    # The key must come from the ELEVENLABS_API_KEY setting in .env,
    # never from a key written into the code.
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="^ELEVENLABS_API_KEY is not set"):
        audio_agent._speech_client()
