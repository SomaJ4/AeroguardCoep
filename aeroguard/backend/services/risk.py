def classify_risk(risk_score: float) -> str:
    """
    Classify a risk score into a risk level.
    < 0.4  → 'low'
    0.4–0.7 inclusive → 'medium'
    > 0.7  → 'high'
    """
    if risk_score < 0.4:
        return "low"
    elif risk_score <= 0.7:
        return "medium"
    else:
        return "high"
