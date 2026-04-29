import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")

HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

# Default PulseAudio/PipeWire source for the mic. Overridable via env so a
# different machine (or a different mic) doesn't need a code change. The
# system default source is unreliable on Linux desktops because it often
# points to a sink monitor instead of a real input device.
MIC_SOURCE = os.environ.get("MEETING_SCRIBE_MIC_SOURCE") or (
    "alsa_input.usb-C-Media_Electronics_Inc._USB_PnP_Sound_Device-00.analog-stereo"
)

VAULT_DIR = Path(
    os.environ.get("MEETING_SCRIBE_VAULT_DIR")
    or str(Path.home() / "Documents" / "Meetings")
)

STATE_DIR = Path.home() / ".local" / "state" / "meeting-scribe"
AUDIO_DIR = STATE_DIR / "audio"
SESSION_FILE = STATE_DIR / "current.json"

WHISPER_MODEL = os.environ.get("MEETING_SCRIBE_WHISPER_MODEL", "large-v3")
WHISPER_DEVICE = os.environ.get("MEETING_SCRIBE_WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE = os.environ.get("MEETING_SCRIBE_WHISPER_COMPUTE", "float16")

DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"

SAMPLE_RATE = 16000
