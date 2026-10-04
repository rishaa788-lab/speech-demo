from pathlib import Path
import streamlit as st

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
