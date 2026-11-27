"""Turn the approved narration for each trip stop into a separate MP3."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import config
from mock_media import make_mock_audio
from models import TripPlan


def _speech_client():
    api_key = config.get_api_key("ELEVENLABS_API_KEY")
    try:
        from elevenlabs.client import ElevenLabs
    except ImportError as exc:
        raise RuntimeError(
            "Install the audio SDK with pip install elevenlabs==2.39.0."
        ) from exc
    return ElevenLabs(api_key=api_key)


def make_voiceovers(plan: TripPlan, run_dir: Path) -> list[Path]:
    """Return one MP3 path per stop, in the order approved by the reviewer."""
    paths = []
    client = None

    for number, stop in enumerate(plan.stops, start=1):
        path = config.audio_path(run_dir, number)
        paths.append(path)
        label = f"[audio] Stop {number} ({stop.name})"

        if path.is_file() and path.stat().st_size > 0:
            print(f"{label}: reusing {path.name}")
            continue

        if not stop.narration.strip():
            raise ValueError(
                f"{label}: add a narration to the plan before generating audio."
            )

        try:
            print(f"{label}: generating {path.name}")
            path.parent.mkdir(parents=True, exist_ok=True)

            if not config.MOCK_MODE and client is None:
                client = _speech_client()

            # Use the final filename only after the recording is complete.
            with NamedTemporaryFile(
                dir=path.parent,
                prefix=path.stem + ".",
                suffix=".partial.mp3",
                delete=False,
            ) as temp:
                partial = Path(temp.name)

            try:
                if config.MOCK_MODE:
                    make_mock_audio(partial, stop.narration)
                else:
                    try:
                        chunks = client.text_to_speech.convert(
                            voice_id=config.ELEVENLABS_VOICE_ID,
                            model_id=config.ELEVENLABS_MODEL,
                            text=stop.narration,
                            output_format="mp3_44100_128",
                        )
                        with partial.open("wb") as output:
                            output.writelines(chunks)
                    except OSError as exc:
                        raise RuntimeError(
                            f"{label}: check the network connection and output folder."
                        ) from exc
                    except Exception as exc:
                        raise RuntimeError(
                            f"{label}: speech generation failed. Check the ElevenLabs key, "
                            "voice, model, quota, and connection before retrying."
                        ) from exc

                if not partial.stat().st_size:
                    raise RuntimeError(f"{label}: received empty audio. Retry this stop.")

                partial.replace(path)
            finally:
                partial.unlink(missing_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"{label}: could not save audio. Check output-folder permissions "
                "and available disk space."
            ) from exc

    return paths
