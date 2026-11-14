"""
audio_agent.py - turns each stop's narration into one voiceover mp3.

Provider: ElevenLabs.

STATUS: mock mode works. The real ElevenLabs call is NOT built yet (TODO: Ankit).

How the work is split:
  - make_voiceovers()           DONE. Loops over the stops, skips files that
                                already exist, and saves safely. The
                                orchestrator calls this.
  - generate_narration_audio()  TODO: Ankit. Turns ONE narration into ONE mp3.
                                This is the only function you need to fill in.

WHY one mp3 per stop (not one long file): assembly needs to know how long
each stop's narration is, so it can make that stop's clip the same length.
"""

from pathlib import Path

import config
import mock_media
from models import TripPlan


def make_voiceovers(plan: TripPlan, run_dir: Path) -> list[Path]:
    """
    Make one mp3 per stop and return their paths, in stop order.

    Files are saved as audio/stop_1.mp3, audio/stop_2.mp3, ...
    If a file already exists (from an earlier run), it is SKIPPED, so a rerun
    never pays for the same audio twice.
    """
    audio_paths = []

    for number, stop in enumerate(plan.stops, start=1):
        final_path = config.audio_path(run_dir, number)

        if final_path.exists():
            print(f"  [audio] Stop {number}: {final_path.name} already exists, skipping.")
        else:
            print(f"  [audio] Stop {number}: making voiceover for {stop.name}...")

            # WHY a temporary ".partial" file: a half-written mp3 from a crash must
            # NOT be mistaken for a finished one on the next run. We only rename it
            # to the real name once it is completely done.
            partial_path = final_path.with_name(f"stop_{number}.partial.mp3")

            if config.MOCK_MODE:
                mock_media.make_mock_audio(partial_path, stop.narration)
            else:
                generate_narration_audio(stop.narration, partial_path)

            partial_path.replace(final_path)  # rename = "this file is finished"

        audio_paths.append(final_path)

    return audio_paths


def generate_narration_audio(text: str, out_path: Path) -> None:
    """
    Turn ONE narration into speech with ElevenLabs and save it as an .mp3.

    Receives:
        text      the stop's narration (about 20 words or fewer)
        out_path  where to save the .mp3 (don't change the name; make_voiceovers()
                  renames it when you're done)
    Must:
        - save a playable .mp3 at out_path
        - return nothing (None)
        - raise an exception with a clear message if anything fails
          (don't save a broken or empty file)
    """
    # ------------------------------------------------------------------
    # TODO: Ankit - replace the line at the bottom with the real ElevenLabs call.
    #
    # Suggested steps (check ElevenLabs' current docs for the exact code):
    #   1. Use the official SDK: pip install elevenlabs (add it to requirements.txt)
    #   2. Get the key with config.get_api_key("ELEVENLABS_API_KEY")
    #   3. Add two settings to config.py AND .env.example:
    #        ELEVENLABS_VOICE_ID   which voice to use (pick one in the ElevenLabs site)
    #        ELEVENLABS_MODEL      which speech model to use
    #   4. Ask for mp3 output, then write all the audio bytes to out_path.
    #
    # Test it with:  pytest tests/test_audio_agent.py   (mock tests)
    # then one real run with a 1-stop trip to keep the cost low.
    # ------------------------------------------------------------------
    raise NotImplementedError(
        "Real ElevenLabs audio isn't built yet (TODO: Ankit). "
        "Run with --mock to use placeholder audio."
    )
