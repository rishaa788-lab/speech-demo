import html
import shutil
import subprocess
import tempfile
import traceback
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


def read_asset(name, default=""):
    for p in (BASE / "static" / name, BASE / name):
        if p.exists():
            return p.read_text(encoding="utf-8")
    return default


MIC_SVG = read_asset(
    "mic.svg",
    '<svg viewBox="0 0 24 24" fill="none" stroke="#219DBC" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="9" y="2" width="6" height="12" rx="3"/>'
    '<path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/></svg>',
)
CSS = read_asset("style.css")
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

# Streamlit-specific layout fixes.
st.markdown(
    """
    <style>
    .block-container { max-width: 1200px; padding-top: 1rem; }
    .stApp { background: var(--bg); color: var(--text); }
    header[data-testid="stHeader"] { display: none; }
    #MainMenu, footer[data-testid="stFooter"] { visibility: hidden; }

    /* icon sizes (no fixed size in the svg itself) */
    .brand-mic { width: 44px; height: 44px; }
    .brand-mic svg, .topbar svg { width: 44px; height: 44px; }
    .upload-icon { display: flex; justify-content: center; margin: 0 0 6px; }
    .upload-icon svg { width: 64px; height: 64px; }

    /* the right-hand card that holds the real upload/record widgets */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-marker) {
      border: 1.5px solid var(--border) !important;
      border-radius: 28px !important;
      background: var(--surface);
      box-shadow: var(--shadow);
      padding: 14px 10px;
    }
    .card-title { text-align: center; margin: 4px 0 2px; font-size: 1.7rem; font-weight: 800; }
    .card-sub { text-align: center; margin: 0 0 12px; opacity: .8; }

    /* blue primary button instead of Streamlit red */
    button[kind="primary"], button[data-testid="stBaseButton-primary"] {
      background: #1d6f9b !important; border: none !important; color: #fff !important;
      border-radius: 14px !important; font-weight: 700 !important; min-height: 52px;
    }
    button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {
      background: #17597d !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "analysis" not in st.session_state:
    st.session_state.analysis = None


def flat(s):
    """Strip indentation/blank lines so Markdown doesn't break the HTML block."""
    return " ".join(line.strip() for line in s.splitlines() if line.strip())


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
    return flat(f"""
    <div class="factor-card">
      <div class="ring {cls}" style="--score:{score:.1f}">
        <div><strong>{round(score)}</strong><small>/100</small></div>
      </div>
      <span>{html.escape(label)}</span>
    </div>
    """)


def metric_card(label, value, small=""):
    small_html = f"<small>{html.escape(small)}</small>" if small else ""
    return flat(f"""
    <div class="metric-card analysis-box">
      <span>{html.escape(label)}</span>
      <strong>{html.escape(str(value))}</strong>
      {small_html}
    </div>
    """)


class NonEnglishError(Exception):
    pass


@st.dialog("English only")
def english_only_dialog():
    st.markdown(
        "<p style='color:red; font-weight:bold;'>"
        "Speech Coach only analyzes <b>English</b> speech right now."
        "</p>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='color:red;'>"
        "Please upload or record your speech in English and try again."
        "</p>",
        unsafe_allow_html=True
    )
    if st.button("OK", use_container_width=True):
        st.rerun()


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


# ---------- TOP BAR ----------
bar_left, bar_mid, bar_right = st.columns([3, 3, 1])
with bar_left:
    st.markdown(
        flat(f"""
        <div class="brand" style="display:flex;align-items:center;gap:12px;">
          <div class="brand-mic">{MIC_SVG}</div>
          <div class="logo">Speech Coach</div>
        </div>
        """),
        unsafe_allow_html=True,
    )
with bar_mid:
    st.markdown(
        '<div class="tagline" style="text-align:right;padding-top:10px;">'
        'Speak better. Present stronger.</div>',
        unsafe_allow_html=True,
    )
with bar_right:
    st.session_state.dark_mode = st.toggle(
        "Dark",
        value=st.session_state.dark_mode,
        key="theme_toggle",
    )

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
        .stApp, .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2 { color: var(--text); }
        [data-testid="stFileUploader"] section,
        [data-testid="stAudioInput"] { background: var(--surface-soft); }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------- HERO: headline on the left, working upload card on the right ----------
left, right = st.columns([1.15, 1], gap="large")

with left:
    st.markdown(
        flat("""
        <section class="hero" style="display:block;min-height:0;padding:3rem 0 0;">
          <p class="eyebrow">AI SPEECH ANALYSIS</p>
          <h1>Improve the way<br>you <span>speak.</span></h1>
          <p class="hero-text">
            Upload or record your speech and get a clear breakdown
            of your delivery, filler words, pace, pauses and more.
          </p>
        </section>
        """),
        unsafe_allow_html=True,
    )

with right:
    with st.container(border=True):
        st.markdown(
            flat(f"""
            <span class="card-marker"></span>
            <div class="upload-icon">{MIC_SVG}</div>
            <div class="card-title">Analyze your speech</div>
            <p class="card-sub">Upload an audio file or record your speech to begin.</p>
            """),
            unsafe_allow_html=True,
        )

        uploaded = st.file_uploader(
            "Choose Audio",
            type=["wav", "mp3", "m4a", "mpeg", "mp4", "webm"],
            label_visibility="collapsed",
            key="audio_upload",
        )
        recorded = st.audio_input("Record", key="audio_record")

        chosen_audio = uploaded if uploaded is not None else recorded
        if chosen_audio is not None:
            st.audio(chosen_audio)
            source = "uploaded file" if uploaded is not None else "recording"
            st.caption(
                f"Analyzing your {source}"
                + (" (remove the upload to use your recording instead)"
                   if uploaded is not None and recorded is not None else "")
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
                with st.spinner("Analyzing speech... this can take a minute"):
                    try:
                        st.session_state.analysis = analyze_uploaded_audio(chosen_audio)
                        st.success("Analysis complete!")
                    except NonEnglishError:
                        st.session_state.analysis = None
                        st.session_state.non_english = True
                    except Exception:
                        st.session_state.analysis = None
                        st.error("The audio could not be analyzed.")
                        # Debug info - delete this expander before final submission.
                        with st.expander("Technical details (for debugging)"):
                            st.code(traceback.format_exc())

        if st.session_state.pop("non_english", False):
            english_only_dialog()

# ---------- RESULTS ----------
data = st.session_state.analysis
if data:
    metrics = data["metrics"]

    st.markdown(
        flat(f"""
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
          </div>
        </section>
        """),
        unsafe_allow_html=True,
    )

    transcript_parts = []
    for item in data["transcript"]:
        word = html.escape(str(item["word"]))
        cls = "word filler" if item.get("filler") else "word"
        transcript_parts.append(f'<span class="{cls}">{word}</span>')

    transcript_html = " ".join(transcript_parts)
    rings = "".join([
        ring_html(metrics["pace_score"], "Pace"),
        ring_html(metrics["volume"], "Volume"),
        ring_html(metrics["filler_score"], "Filler Control"),
        ring_html(metrics["repetition_score"], "Repetition"),
        ring_html(metrics["overall"], "Overall"),
    ])

    st.markdown(
        flat(f"""
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
        """),
        unsafe_allow_html=True,
    )

    def feedback_html(item):
        # generate_feedback returns (title, message) pairs
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            return (
                f'<div class="feedback-item">💡 <strong>{html.escape(str(item[0]))}:'
                f'</strong> {html.escape(str(item[1]))}</div>'
            )
        return f'<div class="feedback-item">💡 {html.escape(str(item))}</div>'

    feedback_items = "".join(feedback_html(item) for item in data["feedback"])
    st.markdown(
        flat(f"""
        <div class="panel analysis-box feedback-panel">
          <p class="eyebrow">ACTIONABLE FEEDBACK</p>
          <h3>What you can improve</h3>
          {feedback_items}
        </div>
        """),
        unsafe_allow_html=True,
    )

st.markdown(
    '<footer>Speech Coach • Multimodal AI Hackathon 2026</footer>',
    unsafe_allow_html=True,
)
