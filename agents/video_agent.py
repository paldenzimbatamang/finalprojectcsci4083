"""
video_agent.py - turns each stop's video_prompt into one SILENT clip.

Provider: Google Veo through Vertex AI (billed to Google Cloud free-trial credits).

STATUS: mock mode works. The real Veo call is NOT built yet (TODO: Dipesh).

How the work is split:
  - make_clips()     DONE. Loops over the stops, skips clips that already
                     exist, and saves safely. The orchestrator calls this.
  - generate_clip()  TODO: Dipesh. Makes ONE clip from ONE prompt. This is
                     the only function you need to fill in.
"""

from pathlib import Path

import config
import mock_media
from models import TripPlan


def make_clips(plan: TripPlan, run_dir: Path) -> list[Path]:
    """
    Make one silent clip per stop and return their paths, in stop order.

    Clips are saved as clips/stop_1.mp4, clips/stop_2.mp4, ...
    If a clip already exists (from an earlier run), it is SKIPPED, so a rerun
    never pays for the same clip twice.
    """
    clip_paths = []

    for number, stop in enumerate(plan.stops, start=1):
        final_path = config.clip_path(run_dir, number)

        if final_path.exists():
            print(f"  [video] Stop {number}: {final_path.name} already exists, skipping.")
        else:
            print(f"  [video] Stop {number}: making clip for {stop.name}...")

            # WHY a temporary ".partial" file: if the program crashes or Veo fails
            # halfway, a half-written file must NOT be mistaken for a finished clip
            # on the next run (it would be skipped forever). We only rename it to
            # the real name once it is completely done.
            partial_path = final_path.with_name(f"stop_{number}.partial.mp4")

            if config.MOCK_MODE:
                mock_media.make_mock_clip(partial_path, number, config.VEO_CLIP_SECONDS)
            else:
                generate_clip(stop.video_prompt, partial_path)

            partial_path.replace(final_path)  # rename = "this clip is finished"

        clip_paths.append(final_path)

    return clip_paths


def generate_clip(prompt: str, out_path: Path) -> None:
    """
    Make ONE real clip with Veo and save it as an .mp4 at out_path.

    Receives:
        prompt    the stop's video_prompt, e.g. "Slow drone shot over ..."
        out_path  where to save the .mp4 (don't change the name; make_clips()
                  renames it when you're done)
    Must:
        - save a playable .mp4 at out_path
        - return nothing (None)
        - raise an exception with a clear message if anything fails
          (don't save a broken or empty file)
    """
    # ------------------------------------------------------------------
    # TODO: Dipesh - replace the line at the bottom with the real Veo call.
    #
    # FIRST TASK: make ONE real test call and find out whether Vertex AI
    # returns the video bytes directly or needs a Cloud Storage bucket for
    # output. If a bucket is needed, add GCS_OUTPUT_BUCKET to config.py and
    # .env.example.
    #
    # Suggested steps (check Google's current docs for the exact code):
    #   1. Use the official SDK: pip install google-genai (add it to requirements.txt)
    #   2. Create a client for Vertex AI (NOT a Gemini API key):
    #        project  = config.get_google_project()
    #        location = config.GOOGLE_CLOUD_LOCATION
    #   3. Start a video job with:
    #        model       = config.VEO_MODEL          (veo-3.1-lite-generate-001)
    #        resolution  = config.VEO_RESOLUTION     (720p)
    #        duration    = config.VEO_CLIP_SECONDS
    #        16:9 aspect ratio, ONE video, and NO audio if the model has that option
    #   4. Veo is slow: the job is "long-running". Check on it every ~10 seconds
    #      until it's done, and give up with a clear error after a few minutes.
    #   5. Save the finished video's bytes to out_path.
    #
    # Don't worry if the clip has sound: assembly removes all audio anyway.
    # Test it with:  pytest tests/test_video_agent.py   (mock tests)
    # then one real run with a 1-stop trip to keep the cost low.
    # ------------------------------------------------------------------
    raise NotImplementedError(
        "Real Veo video generation isn't built yet (TODO: Dipesh). "
        "Run with --mock to use placeholder clips."
    )
