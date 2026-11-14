"""
mock_media.py - makes FAKE video clips and audio files for mock mode.

WHY this exists: mock mode lets us test the whole pipeline without paying
for Veo or ElevenLabs. But assembly still needs real .mp4 and .mp3 files to
join together, so we make cheap placeholder ones with ffmpeg:
  - a clip is a plain colored screen (a different color per stop, so you can
    see the order of the stops in the final preview)
  - an audio file is a simple beep tone

These are real media files, just boring ones. Assembly treats them exactly
like files from the real APIs.
"""

import subprocess
from pathlib import Path

# One color per stop (max 5 stops), so each stop is easy to tell apart.
STOP_COLORS = ["steelblue", "seagreen", "darkorange", "mediumpurple", "firebrick"]

# A typical speaking speed is about 150 words per minute = 2.5 words per second.
# We use it to make mock audio about as long as real speech would be.
WORDS_PER_SECOND = 2.5


def run_ffmpeg(args: list[str]) -> None:
    """
    Run ffmpeg with the given arguments and raise a clear error if it fails.

    WHY a helper: every ffmpeg call needs the same error handling, and the
    raw errors ("FileNotFoundError: 'ffmpeg'") confuse beginners.
    """
    # -y = overwrite without asking; -loglevel error = only print real problems.
    command = ["ffmpeg", "-y", "-loglevel", "error", *args]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg is not installed. Install it (macOS: brew install ffmpeg) and try again."
        ) from None
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"ffmpeg failed:\n{error.stderr}") from None


def make_mock_clip(out_path: Path, stop_number: int, seconds: int) -> None:
    """Make a silent, solid-color 720p clip `seconds` long."""
    color = STOP_COLORS[(stop_number - 1) % len(STOP_COLORS)]
    run_ffmpeg([
        # lavfi lets ffmpeg generate a video from scratch instead of reading a file.
        "-f", "lavfi", "-i", f"color=c={color}:s=1280x720:r=24:d={seconds}",
        "-an",  # no audio track at all, just like the real video agent's clips
        "-c:v", "libx264", "-pix_fmt", "yuv420p",  # the most widely playable mp4 format
        str(out_path),
    ])


def mock_audio_seconds(text: str) -> float:
    """Roughly how long it would take a person to say `text` out loud."""
    words = len(text.split())
    return max(1.0, words / WORDS_PER_SECOND)  # at least 1 second, so the file is never empty


def make_mock_audio(out_path: Path, text: str) -> None:
    """
    Make a beep mp3 about as long as `text` would take to say.

    WHY match the length: a long narration gives a long beep, so mock mode
    also tests assembly's "slow down or freeze the clip to fit" logic.
    """
    seconds = mock_audio_seconds(text)
    run_ffmpeg([
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:a", "libmp3lame", "-q:a", "6",
        str(out_path),
    ])
