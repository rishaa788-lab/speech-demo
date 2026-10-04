import string

import librosa
from faster_whisper import WhisperModel

# ----------------------------- Configuration ----------------------------- #
MODEL_SIZE = "base"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
SAMPLE_RATE = 16000
INITIAL_PROMPT = "Um, uh, so, like, you know, I mean, basically, actually."

# ------------------------------ Model loader ------------------------------ #
_model = None


def get_model():
    """Load the Whisper model once and reuse it."""
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _model


# ------------------------------- Helpers ---------------------------------- #
def load_audio(path):
    """Load an audio file as a mono waveform at the sample rate Whisper expects."""
    return librosa.load(path, sr=SAMPLE_RATE, mono=True)[0]


def build_word_entries(segment):
    """Convert one segment's words into dicts with clean text and timestamps."""
    entries = []

    if not segment.words:
        return entries

    for w in segment.words:
        raw = (w.word or "").strip()
        if not raw:
            continue

        entries.append(
            {
                "word": raw,
                "clean": raw.strip(string.punctuation).lower(),
                "start": round(float(w.start), 2),
                "end": round(float(w.end), 2),
            }
        )

    return entries


# ------------------------------ Public API -------------------------------- #
def transcribe_audio(path):
    """Return transcript, duration, language and word-level timestamps."""
    audio = load_audio(path)

    segments, info = get_model().transcribe(
        audio,
        word_timestamps=True,
        initial_prompt=INITIAL_PROMPT,
    )

    parts = []
    words = []

    for seg in segments:
        text = seg.text.strip()
        if text:
            parts.append(text)
        words.extend(build_word_entries(seg))

    return {
        "text": " ".join(parts),
        "duration": round(float(info.duration), 2),
        "language": info.language,
        "words": words,
    }
