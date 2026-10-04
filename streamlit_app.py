import html
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path

import plotly.graph_objects as go
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
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-marker),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.chart-marker) {
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


def metric_card(label, value, small="", icon=""):
    small_html = f"<small>{html.escape(small)}</small>" if small else ""
    label_text = f"{icon} {label}" if icon else label
    return flat(f"""
    <div class="metric-card analysis-box">
      <span>{html.escape(label_text)}</span>
      <strong>{html.escape(str(value))}</strong>
      {small_html}
    </div>
    """)


class NonEnglishError(Exception):
    pass


@st.dialog("English only")
def english_only_dialog():
    st.markdown(
        '<p style="color:#e74c3c;font-weight:700;font-size:1.1rem;margin:0 0 6px;">'
        'Speech Coach only analyzes English speech right now.</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#e74c3c;margin:0 0 12px;">'
        'Please upload or record your speech in English and try again.</p>',
        unsafe_allow_html=True,
    )
    if st.button("OK", use_container_width=True):
        st.rerun()


def grade_info(score):
    score = max(0, min(100, float(score or 0)))
    if score < 30:
        return "Needs improvement", "#e74c3c"
    if score <= 80:
        return "Developing", "#d99a00"
    return "Strong", "#2fbf71"


def record_attempt(metrics):
    """Keep the last 3 analyses so the user can see progress."""
    n = st.session_state.get("attempt_counter", 0) + 1
    st.session_state.attempt_counter = n
    attempts = st.session_state.get("attempts", [])
    attempts.append({
        "label": f"Attempt {n}",
        "Overall": float(metrics["overall"]),
        "Pace": float(metrics["pace_score"]),
        "Volume": float(metrics["volume"]),
        "Filler Control": float(metrics["filler_score"]),
        "Repetition": float(metrics["repetition_score"]),
    })
    st.session_state.attempts = attempts[-3:]


def progress_figure(attempts, dark):
    text_color = "#edf8fc" if dark else "#1f2d3a"
    grid = "#294a58" if dark else "#e3edf3"
    series = [
        ("Overall", "#EA580C", 5),
        ("Pace", "#4F46E5", 2),
        ("Volume", "#0EA5E9", 2),
        ("Filler Control", "#E11D48", 2),
        ("Repetition", "#16A34A", 2),
    ]
    labels = [a["label"] for a in attempts]
    fig = go.Figure()
    for name, color, width in series:
        fig.add_trace(go.Scatter(
            x=labels, y=[a[name] for a in attempts],
            mode="lines+markers", name=name,
            line=dict(color=color, width=width),
            marker=dict(size=9 if name == "Overall" else 6),
        ))
    fig.update_layout(
        height=340,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=text_color),
        xaxis=dict(showgrid=False, tickfont=dict(color=text_color),
                   linecolor=grid),
        yaxis=dict(range=[0, 105], gridcolor=grid,
                   tickfont=dict(color=text_color),
                   title=dict(text="Score", font=dict(color=text_color))),
        legend=dict(orientation="h", y=-0.15,
                    font=dict(color=text_color, size=13)),
    )
    return fig


def filler_timeline_figure(transcript, duration, dark):
    """Horizontal timeline of the speech with a marker at every filler word."""
    text_color = "#edf8fc" if dark else "#1f2d3a"
    track_color = "#2b414c" if dark else "#d6e4ec"
    fillers = [w for w in transcript if w.get("filler")]

    ends = [w.get("end") or 0 for w in transcript]
    total = float(duration or 0) or (max(ends) if ends else 1.0)
    total = max(total, 1.0)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0, total], y=[0, 0], mode="lines",
        line=dict(color=track_color, width=10),
        hoverinfo="skip", showlegend=False,
    ))
    if fillers:
        show_labels = len(fillers) <= 12
        fig.add_trace(go.Scatter(
            x=[float(w["start"]) for w in fillers],
            y=[0] * len(fillers),
            mode="markers+text" if show_labels else "markers",
            text=[str(w["word"]).strip() for w in fillers],
            textposition="top center",
            textfont=dict(size=12, color=text_color),
            marker=dict(size=16, color="#f2c94c",
                        line=dict(color="#b8860b", width=2)),
            hovertemplate="<b>%{text}</b><br>at %{x:.1f}s<extra></extra>",
            showlegend=False,
        ))
    fig.update_layout(
        height=220,
        margin=dict(l=10, r=10, t=30, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=text_color),
        xaxis=dict(title=dict(text="Time (seconds)",
                              font=dict(color=text_color)),
                   tickfont=dict(color=text_color), range=[0, total],
                   showgrid=False, zeroline=False, linecolor=track_color),
        yaxis=dict(visible=False, range=[-1, 1.6]),
    )
    return fig


def build_pdf(data, attempt_label):
    """Build a detailed PDF report for one analysis and return its bytes."""
    from datetime import datetime
    from io import BytesIO
    from xml.sax.saxutils import escape

    from reportlab.graphics.shapes import Circle, Drawing, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    def clean(text):
        # Built-in PDF fonts only cover Latin-1/CP1252 characters.
        return str(text).encode("cp1252", "replace").decode("cp1252")

    def esc(text):
        return escape(clean(text))

    metrics = data["metrics"]
    transcript = data["transcript"]
    blue = colors.HexColor("#1d6f9b")
    ink = colors.HexColor("#1f2d3a")
    grey = colors.HexColor("#6b7b86")
    line = colors.HexColor("#d6e4ec")
    width = A4[0] - 40 * mm

    title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=22,
                           textColor=blue, leading=26)
    sub = ParagraphStyle("s", fontName="Helvetica", fontSize=10,
                         textColor=grey, leading=14)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14,
                        textColor=ink, spaceBefore=16, spaceAfter=6, leading=18)
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=10,
                          textColor=ink, leading=15)
    small = ParagraphStyle("sm", fontName="Helvetica", fontSize=9,
                           textColor=grey, leading=12)
    big = ParagraphStyle("big", fontName="Helvetica", fontSize=14,
                         textColor=ink, leading=44)
    grade_style = ParagraphStyle("gr", fontName="Helvetica", fontSize=10,
                                 textColor=ink, leading=20)

    story = [
        Paragraph("Speech Coach - Speech Analysis Report", title),
        Spacer(1, 4),
        Paragraph(
            f"{esc(attempt_label)} &bull; "
            f"{datetime.now().strftime('%d %b %Y, %H:%M')}", sub),
        Spacer(1, 12),
    ]

    # Overall score
    overall = float(metrics["overall"])
    grade_text, grade_color = grade_info(overall)
    overall_tbl = Table(
        [[
            Paragraph(
                f'<font size="36" color="{grade_color}"><b>{round(overall)}</b>'
                f'</font><font size="14" color="#6b7b86"> /100</font>', big),
            Paragraph(
                f'<font size="14" color="{grade_color}"><b>{grade_text}</b>'
                f'</font><br/><font color="#6b7b86">Overall delivery score</font>',
                grade_style),
        ]],
        colWidths=[width * 0.4, width * 0.6],
    )
    overall_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, line),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f9fc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    story += [overall_tbl]

    # Key numbers
    story.append(Paragraph("Key numbers", h2))
    rows = [
        ["Total words", metrics["total_words"]],
        ["Filler words", metrics["filler_count"]],
        ["Filler percentage", f'{metrics["filler_percentage"]}%'],
        ["Duration", f'{metrics["duration"]} s'],
        ["Repeated words", metrics["repeated_words"]],
        ["Pace", f'{metrics["pace"]} words/min'],
        ["Volume score", f'{metrics["volume"]}/100'],
    ]
    t = Table([[clean(a), clean(b)] for a, b in rows],
              colWidths=[width * 0.5, width * 0.5])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), ink),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.white, colors.HexColor("#f4f9fc")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, line),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t)

    # Delivery factors
    story.append(Paragraph("Delivery factors", h2))
    factors = [
        ("Pace", metrics["pace_score"]),
        ("Volume", metrics["volume"]),
        ("Filler control", metrics["filler_score"]),
        ("Repetition", metrics["repetition_score"]),
        ("Overall", metrics["overall"]),
    ]
    frows = [["Factor", "Score", "Rating"]]
    for name, score in factors:
        frows.append([name, f"{round(float(score))}/100", grade_info(score)[0]])
    ft = Table(frows, colWidths=[width * 0.4, width * 0.3, width * 0.3])
    style = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), blue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("TEXTCOLOR", (0, 1), (-1, -1), ink),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f4f9fc")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, line),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]
    for i, (_, score) in enumerate(factors, start=1):
        style.append(("TEXTCOLOR", (2, i), (2, i),
                      colors.HexColor(grade_info(score)[1])))
        style.append(("FONTNAME", (2, i), (2, i), "Helvetica-Bold"))
    ft.setStyle(TableStyle(style))
    story.append(ft)
    story.append(Paragraph(
        "Rating guide: below 30 needs improvement, 30 to 80 developing, "
        "above 80 strong.", small))

    # Filler words: timeline + list
    fillers = [w for w in transcript if w.get("filler")]
    story.append(Paragraph("Filler words", h2))
    if not fillers:
        story.append(Paragraph("No filler words detected. Nice and clean!", body))
    else:
        ends = [float(w.get("end") or 0) for w in transcript]
        total = max(float(metrics["duration"] or 0), max(ends) if ends else 0, 1.0)
        draw_w = width
        d = Drawing(draw_w, 52)
        d.add(Rect(0, 24, draw_w, 8, rx=4, ry=4,
                   fillColor=colors.HexColor("#d6e4ec"), strokeColor=None))
        for w in fillers:
            x = min(max(float(w["start"]) / total * draw_w, 6), draw_w - 6)
            d.add(Circle(x, 28, 6, fillColor=colors.HexColor("#f2c94c"),
                         strokeColor=colors.HexColor("#b8860b"), strokeWidth=1))
        d.add(String(0, 6, "0 s", fontName="Helvetica", fontSize=8,
                     fillColor=grey))
        d.add(String(draw_w, 6, f"{total:.0f} s", fontName="Helvetica",
                     fontSize=8, fillColor=grey, textAnchor="end"))
        story.append(d)

        limit = 40
        lrows = [["Time", "Word"]] + [
            [f'{float(w["start"]):.1f} s', clean(str(w["word"]).strip())]
            for w in fillers[:limit]
        ]
        lt = Table(lrows, colWidths=[width * 0.3, width * 0.7])
        lt.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef5f9")),
            ("TEXTCOLOR", (0, 0), (-1, -1), ink),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, line),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story += [Spacer(1, 6), lt]
        if len(fillers) > limit:
            story.append(Paragraph(f"+ {len(fillers) - limit} more", small))

    # Transcript with fillers highlighted
    story.append(Paragraph("Transcript", h2))
    parts = []
    for w in transcript:
        word = esc(w["word"]).strip()
        if w.get("filler"):
            parts.append(f'<font backColor="#f2c94c">{word}</font>')
        else:
            parts.append(word)
    story.append(Paragraph(" ".join(parts) or "No speech detected.", body))
    story.append(Paragraph("Highlighted words are filler words.", small))

    # Feedback
    story.append(Paragraph("What you can improve", h2))
    for item in data["feedback"]:
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            text = f"<b>{esc(item[0])}:</b> {esc(item[1])}"
        else:
            text = esc(item)
        story.append(Paragraph(f"&bull; {text}", body))
        story.append(Spacer(1, 4))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(grey)
        canvas.drawString(20 * mm, 10 * mm,
                          "Speech Coach - Multimodal AI Hackathon 2026")
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buf = BytesIO()
    SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="Speech Coach - Speech Analysis Report",
        author="Speech Coach",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


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
