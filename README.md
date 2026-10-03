# Speech Coach — Streamlit version

This is the Streamlit deployment version of the final Speech Coach project.

## Run locally

```bash
py -m pip install -r requirements.txt
py -m streamlit run streamlit_app.py
```

## Deploy

Use Streamlit Community Cloud:
1. Push this folder to the GitHub repository.
2. Open Streamlit Community Cloud.
3. Select the repository and branch.
4. Set the main file to `streamlit_app.py`.
5. Deploy.

The app keeps the Speech Coach visual system:
- #219DBC primary teal
- #92C9E6 analysis-card outlines
- microphone branding
- light/dark mode
- circular 0–100 delivery-factor rings
- red <30, yellow 30–80, green >80 score logic
- transcript filler highlighting
- Sinchana transcription + timestamps
- Praku filler/hedging analysis
- Ananya 0–100 rubric + feedback
- audio volume/pausing analysis

Note: the Faster-Whisper model downloads on first analysis and may take a little time.
