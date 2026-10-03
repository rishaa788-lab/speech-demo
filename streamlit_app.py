import html
import tempfile
from pathlib import Path

import streamlit as st

from speech_to_text import transcribe_audio
from praku_filler_analysis import analyze_fillers
from ananya_rubric import calculate_rubric, generate_feedback
from audio_features import analyze_audio

st.set_page_config(
    page_title="Speech Coach",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE = Path(__file__).parent
MIC_SVG = (BASE / "static" / "mic.svg").read_text(encoding="utf-8")

# Keep the original Risha visual system.
CSS = (BASE / "static" / "style.css").read_text(encoding="utf-8")
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "analysis" not in st.session_state:
    st.session_state.analysis = None


def score_class(score):
    score = max(0, min(100, float(score or 0)))
    if score < 30:
        return "score-red", "#e74c3c"
    if score <= 80:
        return "score-yellow", "#f2c94c"
    return "score-green", "#2fbf71"


def ring_html(score, label):
    score = max(0, min(100, float(score or 0)))
    cls, _ = score_class(score)
    return f"""
    <div class="factor-card">
      <div class="ring {cls}" style="--score:{score:.1f}">
        <div><strong>{round(score)}</strong><small>/100</small></div>
      </div>
      <span>{html.escape(label)}</span>
    </div>
    """


def metric_card(label, value, small=""):
    return f"""
    <div class="metric-card analysis-box">
      <span>{html.escape(label)}</span>
      <strong>{html.escape(str(value))}</strong>
      {f'<small>{html.escape(small)}</small>' if small else ''}
    </div>
    """


def analyze_uploaded_audio(uploaded):
    suffix = Path(uploaded.name).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getvalue())
        path = Path(tmp.name)

    try:
        # 1) Sinchana: Faster-Whisper + word-level timestamps.
        transcription = transcribe_audio(str(path))
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
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


# ---------- TOP BAR ----------
st.markdown(
    f"""
    <div class="topbar">
      <div class="brand">
        <div class="brand-mic">{MIC_SVG}</div>
        <div class="logo">Speech Coach</div>
      </div>
      <div class="topbar-right">
        <div class="tagline">Speak better. Present stronger.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

toggle_left, toggle_right = st.columns([7, 1])
with toggle_right:
    st.session_state.dark_mode = st.toggle(
        "Dark",
        value=st.session_state.dark_mode,
        key="theme_toggle",
    )

# Streamlit reruns, so apply the dark palette after the toggle.
if st.session_state.dark_mode:
    st.markdown(
        """
        <style>
        :root {
          --bg:#0d1720; --surface:#14232d; --surface-soft:#192c37;
          --text:#edf8fc; --muted:#9fb4bf; --border:#3e91ad;
          --border-soft:#294a58; --primary:#219DBC; --primary-dark:#55bad3;
          --shadow:0 18px 50px rgba(0,0,0,.25); --ring-track:#2b414c;
          --feedback:#183743;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------- HERO ----------
st.markdown(
    f"""
    <div class="container">
      <section class="hero">
        <div>
          <p class="eyebrow">AI SPEECH ANALYSIS</p>
          <h1>Improve the way<br>you <span>speak.</span></h1>
          <p class="hero-text">
            Upload or record your speech and get a clear breakdown
            of your delivery, filler words, pace, pauses and more.
          </p>
        </div>
        <div class="upload-card analysis-box">
          <div class="upload-icon">{MIC_SVG}</div>
          <h2>Analyze your speech</h2>
          <p>Upload an audio file or record your speech to begin.</p>
        </div>
      </section>
    </div>
    """,
    unsafe_allow_html=True,
)

# Put the functional controls immediately below the hero card so the visual layout stays clean.
st.markdown('<div class="container">', unsafe_allow_html=True)
u1, u2 = st.columns(2)
with u1:
    uploaded = st.file_uploader(
        "Choose Audio",
        type=["wav", "mp3", "m4a", "mpeg", "mp4", "webm"],
        label_visibility="collapsed",
        key="audio_upload",
    )
with u2:
    recorded = st.audio_input(
        "Record",
        key="audio_record",
    )

chosen_audio = uploaded if uploaded is not None else recorded
if chosen_audio is not None:
    st.audio(chosen_audio)
    st.caption(
        f"Selected: {getattr(chosen_audio, 'name', 'recorded_speech.wav')}"
    )

analyze = st.button(
    "Analyze Speech →",
    type="primary",
    use_container_width=True,
)

if analyze:
    if chosen_audio is None:
        st.warning("Please choose an audio file or record your speech first.")
    else:
        with st.spinner("Analyzing speech..."):
            try:
                st.session_state.analysis = analyze_uploaded_audio(chosen_audio)
                st.success("Analysis complete!")
            except Exception as exc:
                st.session_state.analysis = None
                st.error("The audio could not be analyzed.")
                st.caption(f"Technical detail: {exc}")

# ---------- RESULTS ----------
data = st.session_state.analysis
if data:
    metrics = data["metrics"]

    st.markdown(
        f"""
        <section class="results">
          <div class="section-heading">
            <div>
              <p class="eyebrow">YOUR RESULTS</p>
              <h2>Speech analysis</h2>
            </div>
            <div class="overall-badge">
              {round(metrics["overall"])}/100
              <small>Overall</small>
            </div>
          </div>

          <div class="metrics-grid">
            {metric_card("Total Words", metrics["total_words"])}
            {metric_card("Filler Words", metrics["filler_count"])}
            {metric_card("Filler %", f'{metrics["filler_percentage"]}%')}
            {metric_card("Duration", f'{metrics["duration"]}s')}
            {metric_card("Repeated Words", metrics["repeated_words"])}
            {metric_card("Pace", metrics["pace"], "words/min")}
            {metric_card("Volume", metrics["volume"], "/100")}
            {metric_card("Pausing", metrics["pausing"], "/100")}
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    # Dashboard row
    transcript_parts = []
    for item in data["transcript"]:
        word = html.escape(str(item["word"]))
        cls = "word filler" if item.get("filler") else "word"
        transcript_parts.append(f'<span class="{cls}">{word}</span>')

    transcript_html = "".join(transcript_parts)
    rings = "".join([
        ring_html(metrics["pace"], "Pace"),
        ring_html(metrics["volume"], "Volume"),
        ring_html(metrics["pausing"], "Pausing"),
        ring_html(metrics["filler_score"], "Filler Control"),
        ring_html(metrics["repetition_score"], "Repetition"),
        ring_html(metrics["overall"], "Overall"),
    ])

    st.markdown(
        f"""
        <div class="dashboard-grid">
          <div class="panel analysis-box transcript-panel">
            <div class="panel-title">
              <div>
                <p class="eyebrow">TRANSCRIPT</p>
                <h3>Your speech</h3>
              </div>
              <span class="legend">🟡 Filler word</span>
            </div>
            <div class="transcript">{transcript_html}</div>
          </div>

          <div class="panel analysis-box delivery-panel">
            <div class="panel-title">
              <div>
                <p class="eyebrow">IMPROVEMENT TRACKER</p>
                <h3>Delivery factors</h3>
              </div>
            </div>
            <div class="factor-grid">{rings}</div>
            <div class="score-legend">
              <span><i class="dot red"></i>Needs improvement &lt;30</span>
              <span><i class="dot yellow"></i>Developing 30–80</span>
              <span><i class="dot green"></i>Strong &gt;80</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    feedback_items = "".join(
        f'<div class="feedback-item">💡 {html.escape(str(item))}</div>'
        for item in data["feedback"]
    )
    st.markdown(
        f"""
        <div class="panel analysis-box feedback-panel">
          <p class="eyebrow">ACTIONABLE FEEDBACK</p>
          <h3>What you can improve</h3>
          {feedback_items}
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    '<footer>Speech Coach • Multimodal AI Hackathon 2026</footer>',
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)
