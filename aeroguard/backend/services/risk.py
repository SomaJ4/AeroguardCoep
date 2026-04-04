def classify_risk(risk_score: float) -> str:
    """
    Classify a risk score into a risk level (testing thresholds).
    < 0.05        → 'low'    (no dispatch)
    0.05 – 0.08   → 'medium' (manual dispatch alert)
    > 0.08        → 'high'   (auto-dispatch drone)
    """
    if risk_score < 0.05:
        return "low"
    elif risk_score <= 0.08:
        return "medium"
    else:
        return "high"
