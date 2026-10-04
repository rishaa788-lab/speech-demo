import streamlit as st

from .ui_helpers import flat

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

