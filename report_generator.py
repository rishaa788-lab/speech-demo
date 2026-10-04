import html

from backend.scoring import grade_info

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
