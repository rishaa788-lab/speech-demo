import shutil
import subprocess
import tempfile
from pathlib import Path

from speech_to_text import transcribe_audio
from praku_filler_analysis import analyze_fillers
from ananya_rubric import calculate_rubric, generate_feedback
from audio_features import analyze_audio

class NonEnglishError(Exception):
    pass
def to_clean_wav(src):
    """Convert any uploaded/recorded audio to a real 16 kHz mono WAV with ffmpeg.
    Fixes files whose extension doesn't match their real format."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return src  # no ffmpeg available: try the original file
    out = src.with_name(src.stem + "_clean.wav")
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(out)],
        capture_output=True,
    )
    if result.returncode != 0 or not out.exists():
        tail = result.stderr.decode("utf-8", "ignore")[-400:]
        raise RuntimeError("ffmpeg could not read this audio file: " + tail)
    return out


def analyze_uploaded_audio(uploaded):
    suffix = Path(getattr(uploaded, "name", "") or "").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getvalue())
        raw_path = Path(tmp.name)

    path = raw_path
    try:
        path = to_clean_wav(raw_path)

        # 1) Sinchana: Faster-Whisper + word-level timestamps.
        transcription = transcribe_audio(str(path))

        lang = str(transcription.get("language") or "").lower()
        if lang and not lang.startswith("en"):
            raise NonEnglishError()

        words = transcription["words"]

        # 2) Praku: timestamp-aware filler + hedging detection.
        filler_result = analyze_fillers(words)
        filler_occurrences = filler_result["fillers"]
        filler_indices = set()
        for occurrence in filler_occurrences:
            filler_indices.update(
                occurrence.get("indices", [occurrence.get("index")])
            )

        transcript_words = []
        for i, word in enumerate(words):
            transcript_words.append({
                "word": word["word"],
                "clean": word["clean"],
                "start": word["start"],
                "end": word["end"],
                "filler": i in filler_indices,
            })

        # 3) Audio-level volume + pause analysis.
        audio_metrics = analyze_audio(
            path, words, transcription["duration"]
        )

        # 4) Ananya: 0-100 rubric + feedback.
        rubric = calculate_rubric(
            transcription["text"],
            filler_words=filler_occurrences,
            duration_seconds=transcription["duration"],
            volume_score=audio_metrics["volume_score"],
            pausing_score=audio_metrics["pausing_score"],
        )

        return {
            "transcript": transcript_words,
            "text": transcription["text"],
            "language": transcription["language"],
            "hedging": filler_result["hedging"],
            "fillers": filler_occurrences,
            "pause_intervals": audio_metrics["pause_intervals"],
            "metrics": {
                "total_words": rubric["total_words"],
                "filler_count": rubric["filler_count"],
                "filler_percentage": rubric["filler_percentage"],
                "duration": rubric["duration_seconds"],
                "repeated_words": rubric["repeated_count"],
                "pace": rubric["pace_wpm"],
                "volume": rubric["volume_score"],
                "pausing": rubric["pausing_score"],
                "overall": rubric["overall"],
                "filler_score": rubric["filler_score"],
                "repetition_score": rubric["repetition_score"],
                "pace_score": rubric["pace_score"],
            },
            "feedback": generate_feedback(rubric),
        }
    finally:
        for f in {raw_path, path}:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
