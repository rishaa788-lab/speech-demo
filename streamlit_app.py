import html
import traceback
import streamlit as st

from frontend.styles import MIC_SVG
from frontend.ui_helpers import flat, metric_card, ring_html, grade_info, record_attempt
from frontend.charts import progress_figure, filler_timeline_figure
from frontend.components import english_only_dialog
from backend.analysis_service import analyze_uploaded_audio
from backend.report_generator import build_pdf

st.set_page_config(
    page_title="Speech Coach",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------- SESSION STATE ----------
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True  # dark by default; users can switch to light
if "analysis" not in st.session_state:
    st.session_state.analysis = None

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
        button[kind="secondary"], button[data-testid="stBaseButton-secondary"] {
          background: var(--surface-soft) !important;
          border: 1px solid var(--border) !important;
        }
        button[kind="secondary"] p, button[data-testid="stBaseButton-secondary"] p {
          color: var(--text) !important;
        }
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
                        record_attempt(st.session_state.analysis["metrics"])
                        n_attempt = st.session_state.attempt_counter
                        try:
                            st.session_state.pdf_report = {
                                "bytes": build_pdf(
                                    st.session_state.analysis,
                                    f"Attempt {n_attempt}",
                                ),
                                "name": f"speech_analysis_attempt_{n_attempt}.pdf",
                            }
                        except Exception:
                            st.session_state.pdf_report = None
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
    grade_text, grade_color = grade_info(metrics["overall"])

    st.markdown(
        flat(f"""
        <section class="results">
          <div class="section-heading">
            <div>
              <p class="eyebrow">YOUR RESULTS</p>
              <h2>Speech analysis</h2>
              <span style="display:inline-block;padding:4px 14px;border-radius:999px;font-weight:700;font-size:.85rem;color:#fff;background:{grade_color};">{grade_text}</span>
            </div>
            <div class="overall-badge">
              {round(metrics["overall"])}/100
              <small>Overall</small>
            </div>
          </div>

          <div class="metrics-grid">
            {metric_card("Total Words", metrics["total_words"], icon="📝")}
            {metric_card("Filler Words", metrics["filler_count"], icon="🟡")}
            {metric_card("Filler %", f'{metrics["filler_percentage"]}%', icon="📊")}
            {metric_card("Duration", f'{metrics["duration"]}s', icon="⏱️")}
            {metric_card("Repeated Words", metrics["repeated_words"], icon="🔁")}
            {metric_card("Pace", metrics["pace"], "words/min", icon="⚡")}
            {metric_card("Volume", metrics["volume"], "/100", icon="🔊")}
          </div>
        </section>
        """),
        unsafe_allow_html=True,
    )

    report = st.session_state.get("pdf_report")
    if report:
        st.download_button(
            "⬇️ Download PDF report",
            data=report["bytes"],
            file_name=report["name"],
            mime="application/pdf",
            type="primary",
            use_container_width=True,
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

    with st.container(border=True):
        st.markdown(
            flat("""
            <span class="chart-marker"></span>
            <p class="eyebrow">FILLER TIMELINE</p>
            <h3>When you used filler words</h3>
            """),
            unsafe_allow_html=True,
        )
        if metrics["filler_count"] == 0 or not any(
            w.get("filler") for w in data["transcript"]
        ):
            st.success("No filler words detected. Nice and clean!")
        else:
            st.plotly_chart(
                filler_timeline_figure(
                    data["transcript"],
                    metrics["duration"],
                    st.session_state.dark_mode,
                ),
                use_container_width=True,
                theme=None,
                config={"displayModeBar": False},
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

    attempts = st.session_state.get("attempts", [])
    if attempts:
        with st.container(border=True):
            st.markdown(
                flat("""
                <span class="chart-marker"></span>
                <p class="eyebrow">PROGRESS ACROSS ATTEMPTS</p>
                <h3>Are you improving?</h3>
                """),
                unsafe_allow_html=True,
            )
            if len(attempts) >= 2:
                diff = attempts[-1]["Overall"] - attempts[-2]["Overall"]
                if diff > 0:
                    arrow, color = "▲", "#2fbf71"
                elif diff < 0:
                    arrow, color = "▼", "#e74c3c"
                else:
                    arrow, color = "■", "#8a99a3"
                st.markdown(
                    f'<p style="font-weight:700;color:{color};margin:0 0 4px;">'
                    f'{arrow} Overall {diff:+.1f} vs your last attempt</p>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption(
                    "Analyze another recording to see your progress. "
                    "The last 3 attempts are kept while this page stays open."
                )
            st.plotly_chart(
                progress_figure(attempts, st.session_state.dark_mode),
                use_container_width=True,
                theme=None,
                config={"displayModeBar": False},
            )
            if st.button("Reset attempts"):
                st.session_state.attempts = []
                st.session_state.attempt_counter = 0
                st.rerun()

st.markdown(
    '<footer>Speech Coach • Multimodal AI Hackathon 2026</footer>',
    unsafe_allow_html=True,
)
