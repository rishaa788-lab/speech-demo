# Speech Coach — Clean Architecture

This version reorganizes the original Streamlit application without rewriting its existing analysis/UI logic.

## Structure

```text
speech_coach_clean/
├── app.py                         # Streamlit entry point / page orchestration
├── frontend/
│   ├── components.py              # Streamlit dialogs/components
│   ├── charts.py                  # Plotly chart builders
│   ├── styles.py                  # CSS/assets loading
│   └── ui_helpers.py              # Reusable UI helpers and session progress state
├── backend/
│   ├── analysis_service.py        # Audio preprocessing + analysis pipeline
│   └── report_generator.py        # PDF report generation
├── static/
│   ├── style.css                  # Put your existing CSS here
│   └── mic.svg                    # Put your existing microphone SVG here
├── speech_to_text.py              # Your existing module — keep unchanged
├── praku_filler_analysis.py       # Your existing module — keep unchanged
├── ananya_rubric.py               # Your existing module — keep unchanged
├── audio_features.py              # Your existing module — keep unchanged
└── requirements.txt
```

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important

The four analysis modules are intentionally not rewritten because they were not included in the uploaded file. Replace the placeholder files in this package with your original versions, unchanged.

The existing `static/style.css` and `static/mic.svg` assets should also be copied into `static/` if they exist in your current project.

## Architecture

- **Frontend:** Streamlit presentation, styling, reusable UI helpers, and charts.
- **Backend:** audio-processing pipeline and PDF report generation.
- **Entry point:** `app.py` coordinates the frontend and backend.
- **Analysis modules:** remain independent backend dependencies.
