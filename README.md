#  Speech Coach

**Speech Coach** is an AI-powered speech analysis application built for the **Multimodal AI Hackathon 2026**.

It helps users improve their speaking and presentation delivery by analyzing an uploaded or recorded speech and providing a clear breakdown of:

-  Speech transcription
-  Filler words
-  Filler-word percentage
-  Speaking pace
-  Voice volume
-  Pausing
-  Repeated words
-  Overall delivery score
-  Actionable improvement feedback
-  Progress across multiple attempts
-  Downloadable PDF analysis reports

The application currently analyzes **English speech**.

---

##  Key Features

###  Upload or Record Speech
Users can either upload an audio file or record speech directly through the application.

Supported upload formats include:

`WAV`, `MP3`, `M4A`, `MPEG`, `MP4`, and `WEBM`.

###  Speech-to-Text Analysis
The speech is transcribed with word-level timing information. These timestamps are used by the downstream analysis modules.

###  Filler Word Detection
The application identifies filler words and tracks when they occur during the speech.

The results include:

- Number of filler words
- Filler-word percentage
- Filler-control score
- A visual filler-word timeline
- Highlighted filler words in the transcript

###  Audio Analysis
The audio is processed to evaluate delivery characteristics including:

- Volume
- Pausing
- Duration

###  Speech Scoring
The speech is evaluated using a 0–100 scoring system covering:

- Pace
- Volume
- Filler control
- Repetition
- Overall delivery

Scores are also grouped into:

| Score | Rating |
|---|---|
| Below 30 | Needs improvement |
| 30–80 | Developing |
| Above 80 | Strong |

###  Actionable Feedback
The application generates feedback based on the analysis so the user can understand what to improve.

###  Improvement Tracker
The last three attempts are retained while the page remains open, allowing users to compare their progress over multiple recordings.

###  PDF Reports
Users can download a detailed PDF report containing:

- Overall score
- Key speech metrics
- Delivery-factor scores
- Filler-word timeline
- Transcript
- Improvement feedback

###  Dark / Light Interface
The Streamlit interface includes a theme toggle and a custom-designed visual interface.

---

#  Project Architecture

The project is organized into separate frontend, backend/service, and analysis modules.

```text
Speech-Coach/
│
├── app.py
│
├── backend/
│   ├── __init__.py
│   ├── analysis_service.py
│   ├── report_generator.py
│   └── scoring.py
│
├── frontend/
│   ├── __init__.py
│   ├── components.py
│   ├── charts.py
│   ├── styles.py
│   ├── ui_helpers.py
│   │
│   └── static/
│       └── style.css
│
├── ananya_rubric.py
├── audio_features.py
├── praku_filler_analysis.py
├── speech_to_text.py
│
├── requirements.txt
├── packages.txt
├── README.md
│
└── .streamlit/
    └── config.toml
```

##  Module Responsibilities

### `app.py`
The main Streamlit application entry point.

It connects the user interface with the analysis services and displays the results.

### `frontend/`
Contains the presentation layer of the application.

- `components.py` — reusable Streamlit UI components and dialogs
- `charts.py` — Plotly visualizations
- `styles.py` — frontend styling and CSS integration
- `ui_helpers.py` — reusable UI/HTML helpers
- `static/style.css` — custom application styling

### `backend/`
Contains reusable application services.

- `analysis_service.py` — coordinates the speech-analysis pipeline
- `report_generator.py` — generates downloadable PDF reports
- `scoring.py` — handles scoring/rating-related logic

### AI / Analysis Modules

The core analysis modules are kept as independent components:

- `speech_to_text.py` — speech transcription
- `praku_filler_analysis.py` — filler and hedging analysis
- `audio_features.py` — audio-level analysis such as volume and pauses
- `ananya_rubric.py` — rubric-based scoring and feedback generation

This separation keeps the analysis components independent from the Streamlit presentation layer.

---

#  Analysis Pipeline

The application follows this general flow:

```text
User uploads / records speech
            │
            ▼
      Audio preprocessing
            │
            ▼
       Speech-to-text
            │
            ▼
   Word-level transcription
            │
      ┌─────┴─────┐
      ▼           ▼
Filler analysis  Audio analysis
      │           │
      └─────┬─────┘
            ▼
      Rubric / Scoring
            │
            ▼
     Feedback generation
            │
      ┌─────┴───────────┐
      ▼                 ▼
 Results dashboard   PDF report
```

Before analysis, uploaded/recorded audio can be converted to a **16 kHz mono WAV** using FFmpeg when FFmpeg is available.

---

#  Tech Stack

- **Python**
- **Streamlit** — interactive web application
- **Plotly** — charts and visualizations
- **ReportLab** — PDF report generation
- **FFmpeg** — audio preprocessing
- Speech-to-text and custom analysis modules included in the project

The exact Python dependencies are listed in `requirements.txt`.

---

#  Running the Application Locally

## 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd Speech-Coach
```

## 2. Create a virtual environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

## 4. Make sure FFmpeg is available

The application uses FFmpeg for audio preprocessing when it is available.

For deployment environments that support system packages, `packages.txt` can be used for the required system dependency.

## 5. Start the application

```bash
streamlit run app.py
```

The Streamlit server will provide a local URL where the application can be opened in a browser.

---

#  Usage

1. Open Speech Coach.
2. Upload an audio file **or** record speech.
3. Click **Analyze Speech**.
4. Wait for the speech analysis to complete.
5. Review the overall score and individual delivery metrics.
6. Read the transcript with filler words highlighted.
7. Explore the filler-word timeline.
8. Review actionable feedback.
9. Analyze another recording to compare attempts.
10. Download the detailed PDF report.

---

#  Language Support

Speech Coach currently analyzes **English speech only**.

If non-English speech is detected, the application displays an English-only message and asks the user to provide an English recording.

---

#  Results Dashboard

After analysis, the dashboard presents:

```text
Overall Score
      │
      ├── Total Words
      ├── Filler Words
      ├── Filler %
      ├── Duration
      ├── Repeated Words
      ├── Pace
      └── Volume

Transcript
      │
      └── Filler words highlighted

Delivery Factors
      │
      ├── Pace
      ├── Volume
      ├── Filler Control
      ├── Repetition
      └── Overall

Filler Timeline
      │
      └── Filler occurrences over speech duration

Actionable Feedback
      │
      └── Personalized improvement suggestions

Progress Tracker
      │
      └── Comparison of recent attempts
```

---

#  Project Structure for the Hackathon

The project follows a modular architecture so that different parts of the system can be developed and maintained independently.

```text
Presentation Layer
        │
        ▼
Frontend / Streamlit
        │
        ▼
Backend Services
        │
        ▼
Analysis Modules
        │
        ├── Speech-to-Text
        ├── Filler Analysis
        ├── Audio Analysis
        └── Rubric / Feedback
```

This separation makes the application easier to understand, test, maintain, and extend.

---

#  Future Improvements

Potential future improvements include:

- Support for additional languages
- More detailed pronunciation analysis
- More advanced speaking-pattern analysis
- Persistent user history
- Long-term progress tracking
- Additional presentation and communication metrics
- More detailed visual analytics

---

#  Hackathon

**Speech Coach — Multimodal AI Hackathon 2026**

The project combines speech transcription, language analysis, audio analysis, scoring, visualization, and report generation into a single speech-improvement workflow.

---

##  License

This project was created as a hackathon project.
