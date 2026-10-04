def grade_info(score):
    score = max(0, min(100, float(score or 0)))
    if score < 30:
        return "Needs improvement", "#e74c3c"
    if score <= 80:
        return "Developing", "#d99a00"
    return "Strong", "#2fbf71"

