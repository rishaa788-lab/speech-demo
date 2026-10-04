import plotly.graph_objects as go

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
        margin=dict(l=60, r=20, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=text_color),
        xaxis=dict(showgrid=False, tickfont=dict(color=text_color),
                   linecolor=grid, automargin=True),
        yaxis=dict(range=[0, 105], gridcolor=grid, automargin=True,
                   tickfont=dict(color=text_color),
                   title=dict(text="Score", standoff=14,
                              font=dict(color=text_color))),
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
