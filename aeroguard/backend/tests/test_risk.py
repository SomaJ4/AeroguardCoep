# Feature: aeroguard-platform, Property 1: Risk Classification Correctness
from hypothesis import given, settings
from hypothesis import strategies as st
from services.risk import classify_risk


@given(st.floats(min_value=0.0, max_value=1.0))
@settings(max_examples=20)
def test_risk_classification_correctness(score):
    """Validates: Requirements 3.1, 3.2, 3.3, 3.5, 3.6"""
    result = classify_risk(score)
    if score < 0.4:
        assert result == "low"
    elif score <= 0.7:
        assert result == "medium"
    else:
        assert result == "high"


def test_boundary_04():
    assert classify_risk(0.4) == "medium"


def test_boundary_07():
    assert classify_risk(0.7) == "medium"


def test_just_below_04():
    assert classify_risk(0.399) == "low"


def test_just_above_07():
    assert classify_risk(0.701) == "high"
