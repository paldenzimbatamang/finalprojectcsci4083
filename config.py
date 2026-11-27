"""
config.py - settings shared by every part of the pipeline.

It does four jobs:
  1. Reads API keys from the .env file (which is never committed to git).
  2. Holds the MOCK_MODE switch, so we can test without paying for API calls.
  3. Creates a fresh output folder for each run.
  4. Decides the file names for clips and audio, so the video agent, the
     audio agent and assembly all agree on where files live.

IMPORTANT for teammates: read settings as `config.MOCK_MODE`, NOT
`from config import MOCK_MODE`. The second form copies the value once at
import time, so if main.py turns mock mode on later, your file won't see it.
"""

import os
from datetime import datetime
from pathlib import Path

# The folder this file lives in = the project root. Using this instead of
# the "current directory" means paths work no matter where you run python from.
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
ENV_FILE = PROJECT_ROOT / ".env"


# ---------- 1. Reading the .env file ----------

def load_env_file(path: Path = ENV_FILE) -> None:
    """
    Read KEY=value lines from .env into environment variables.

    WHY we wrote this ourselves instead of installing python-dotenv: it's
    about 10 lines, and CLAUDE.md asks us to avoid unnecessary libraries.

    Rules: blank lines and lines starting with # are skipped. Quotes around
    a value are removed. A variable that's already set in your terminal wins
    over the .env file, so you can override a setting for one run.
    """
    if not path.exists():
        return  # Fine in mock mode; get_api_key() will complain if a key is really needed.

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)  # split on the FIRST "=" only; keys may contain "=" in the value
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)  # setdefault = don't overwrite what's already set


# Load .env as soon as any file does `import config`.
load_env_file()


# ---------- 2. Mock mode ----------

# True when MOCK_MODE=1 (or true/yes) in .env or the terminal.
# main.py will also set this to True when you pass --mock.
MOCK_MODE = os.environ.get("MOCK_MODE", "0").strip().lower() in ("1", "true", "yes")

# Which Claude model each agent uses. Change them in .env without touching code.
# The planner uses Sonnet because picking stops and writing short prompts is a
# simple task, and Sonnet costs half as much as Opus.
PLANNER_MODEL = os.environ.get("PLANNER_MODEL", "claude-sonnet-5-5")
# The text agent's model (decided when we build the text agent).
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

# Video agent settings (Google Veo through Vertex AI).
# WHY Vertex AI and not a Gemini API key: Vertex bills our Google Cloud
# project, so it can use the free-trial credits. Vertex doesn't use an API
# key at all; it logs in with Application Default Credentials, which you set
# up once with:  gcloud auth application-default login
# The variable names below are the same ones Google's own library reads.
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")  # your project ID; no safe default
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")  # the region Veo runs in
# Veo 3.1 Lite at 720p is the cheapest option. Change these in .env if needed.
VEO_MODEL = os.environ.get("VEO_MODEL", "veo-3.1-lite-generate-001")
VEO_RESOLUTION = os.environ.get("VEO_RESOLUTION", "720p")
# How long each Veo clip is, in seconds. Veo only accepts a few fixed lengths;
# Dipesh: check which ones Veo 3.1 Lite allows and update this default if needed.
VEO_CLIP_SECONDS = int(os.environ.get("VEO_CLIP_SECONDS", "8"))


ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# Narration length cap (team decision): about 20 words is roughly 8 seconds of
# speech, which matches one 8-second clip. The text agent tells Claude to stay
# under this. If a narration still runs longer than its clip, assembly slows or
# freezes the clip to fit, so nothing gets cut off.
NARRATION_MAX_WORDS = 20


def get_api_key(name: str) -> str:
    """
    Return the API key called `name` (e.g. "ANTHROPIC_API_KEY").

    WHY a function instead of reading os.environ directly: if the key is
    missing we want ONE clear message that says how to fix it, not a
    confusing error from deep inside the API library.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in, "
            f"or run with --mock to skip real API calls."
        )
    return value


def get_google_project() -> str:
    """
    Return the Google Cloud project ID for the video agent.

    Same idea as get_api_key(): fail early with a clear fix-it message.
    It's a separate function because Vertex needs a project ID, not a key.
    """
    if not GOOGLE_CLOUD_PROJECT.strip():
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT is not set. Put your Google Cloud project ID in .env, "
            "run `gcloud auth application-default login` once, "
            "or run with --mock to skip real API calls."
        )
    return GOOGLE_CLOUD_PROJECT.strip()


# ---------- 3. One folder per run ----------

def new_run_dir() -> Path:
    """
    Create and return a new folder like output/2026-11-14_153012/.

    WHY one folder per run: results from different trips never overwrite
    each other, and each folder holds everything for that run (plan, clips,
    audio, log, final videos), which makes the report and demo easier.
    """
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = OUTPUT_DIR / stamp
    (run_dir / "clips").mkdir(parents=True, exist_ok=False)  # exist_ok=False: never reuse a folder by accident
    (run_dir / "audio").mkdir()
    return run_dir


# ---------- 4. Agreed file names ----------
# Stop numbers start at 1 to match what the reviewer sees ("Stop 1").
# The video agent and audio agent use these to decide where to save, and
# use .exists() on them to skip files that were already made (so a rerun
# doesn't pay for the same clip twice). Assembly uses them to find the files.

def plan_path(run_dir: Path) -> Path:
    return run_dir / "plan.json"


def clip_path(run_dir: Path, stop_number: int) -> Path:
    return run_dir / "clips" / f"stop_{stop_number}.mp4"


def audio_path(run_dir: Path, stop_number: int) -> Path:
    return run_dir / "audio" / f"stop_{stop_number}.mp3"


def run_log_path(run_dir: Path) -> Path:
    return run_dir / "run_log.csv"
