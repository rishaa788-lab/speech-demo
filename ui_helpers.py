import html
import streamlit as st

from backend.scoring import grade_info

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
