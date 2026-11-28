"""Run the audio agent alone with free, local beep recordings."""

import argparse
from pathlib import Path

import config
from agents.audio_agent import make_voiceovers
from models import Stop, TripPlan


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--narration", action="append",
        help="Narration to simulate; repeat this option for multiple stops.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=config.OUTPUT_DIR / "audio_mock",
        help="Run folder (default: output/audio_mock). Existing audio is reused.",
    )
    args = parser.parse_args(argv)
    narrations = args.narration or [
        "Welcome to Mobile. Enjoy the waterfront and historic streets.",
        "Next, explore the Biloxi waterfront and its lighthouse.",
    ]
    if any(not text.strip() for text in narrations):
        parser.error("Each narration must contain some text.")
    plan = TripPlan(
        trip_text="Standalone mock audio test",
        stops=[Stop(name=f"Mock stop {n}", narration=text)
               for n, text in enumerate(narrations, start=1)],
    )

    # Force mock mode even if .env says MOCK_MODE=0. Never create an API client.
    previous_mode = config.MOCK_MODE
    config.MOCK_MODE = True
    try:
        print("Mock audio only: local beeps, no API calls or credits.")
        for path in make_voiceovers(plan, args.output_dir):
            print(path.resolve())
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"Audio test failed: {exc}\n")
    finally:
        config.MOCK_MODE = previous_mode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
