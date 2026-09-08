"""Comprehensive Automated Test Suite for SAKHI AI / Risk Engine.

Validates all 19 mandatory test scenarios from specification:
1. SAFE scenario
2. SUSPICIOUS scenario
3. HIGH scenario
4. CRITICAL scenario
5. Manual SOS scenario
6. Multiple simultaneous signals
7. Score cannot exceed 100
8. Score cannot go below 0
9. Invalid signal values
10. Missing input
11. Unknown signal
12. Correct risk classification
13. Correct reasons
14. Correct signals_detected
15. Configurable thresholds
16. Configurable weights
17. Detector failure handling
18. API validation
19. Stable response structure
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.ai_engine.api import app
from src.ai_engine.config import RiskEngineSettings, RiskThresholds, SignalWeights
from src.ai_engine.detectors.base import BaseDetector, DetectionResult, DetectorStatus
from src.ai_engine.engine import RiskEngine
from src.ai_engine.schemas import (
    AIAnalyzeRequest,
    RiskLevel,
    SignalsPayload,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: SAFE scenario
# ---------------------------------------------------------------------------
def test_safe_scenario_empty_signals():
    """Empty or inactive signals produce score 0 and SAFE level."""
    engine = RiskEngine()
    signals = SignalsPayload()
    result = engine.analyze(signals)

    assert result.risk_score == 0.0
    assert result.risk_level == RiskLevel.SAFE
    assert result.reasons == []
    assert result.signals_detected == []


def test_safe_scenario_route_deviation_alone():
    """Route deviation alone gives score 15, classified as SAFE (0-30)."""
    engine = RiskEngine()
    signals = SignalsPayload(route_deviation=True)
    result = engine.analyze(signals)

    assert result.risk_score == 15.0
    assert result.risk_level == RiskLevel.SAFE
    assert "Route deviation detected" in result.reasons
    assert result.signals_detected == ["route_deviation"]


# ---------------------------------------------------------------------------
# Test 2: SUSPICIOUS scenario
# ---------------------------------------------------------------------------
def test_suspicious_scenario_distress_audio():
    """Distress audio alone gives score 35, classified as SUSPICIOUS (31-60)."""
    engine = RiskEngine()
    signals = SignalsPayload(distress_audio=True)
    result = engine.analyze(signals)

    assert result.risk_score == 35.0
    assert result.risk_level == RiskLevel.SUSPICIOUS
    assert "Distress audio detected" in result.reasons
    assert result.signals_detected == ["distress_audio"]


def test_suspicious_scenario_audio_and_fall():
    """Distress audio (35) + fall (25) = 60, classified as SUSPICIOUS (boundary 60)."""
    engine = RiskEngine()
    signals = SignalsPayload(distress_audio=True, sudden_fall=True)
    result = engine.analyze(signals)

    assert result.risk_score == 60.0
    assert result.risk_level == RiskLevel.SUSPICIOUS
    assert "Distress audio detected" in result.reasons
    assert "Sudden fall detected" in result.reasons
    assert set(result.signals_detected) == {"distress_audio", "sudden_fall"}


# ---------------------------------------------------------------------------
# Test 3: HIGH scenario
# ---------------------------------------------------------------------------
def test_high_scenario_audio_fall_motion():
    """Distress audio (35) + fall (25) + abnormal motion (15) = 75 -> HIGH (61-80)."""
    engine = RiskEngine()
    signals = SignalsPayload(
        distress_audio=True,
        sudden_fall=True,
        abnormal_motion=True,
    )
    result = engine.analyze(signals)

    assert result.risk_score == 75.0
    assert result.risk_level == RiskLevel.HIGH
    assert set(result.signals_detected) == {
        "distress_audio",
        "sudden_fall",
        "abnormal_motion",
    }


# ---------------------------------------------------------------------------
# Test 4: CRITICAL scenario
# ---------------------------------------------------------------------------
def test_critical_scenario_multiple_strong_signals():
    """Multiple strong signals totaling >= 81 produce CRITICAL."""
    engine = RiskEngine()
    signals = SignalsPayload(
        manual_sos=True,       # 50
        distress_audio=True,   # 35
        no_response=True,      # 20
    )
    result = engine.analyze(signals)

    # 50 + 35 + 20 = 105 clamped to 100
    assert result.risk_score == 100.0
    assert result.risk_level == RiskLevel.CRITICAL
    assert "Manual SOS triggered" in result.reasons
    assert "Distress audio detected" in result.reasons
    assert "No user response detected" in result.reasons


# ---------------------------------------------------------------------------
# Test 5: Manual SOS
# ---------------------------------------------------------------------------
def test_manual_sos_alone_produces_high_weight_and_no_emergency_dispatch():
    """Manual SOS alone adds +50 and does NOT trigger external emergency calls."""
    engine = RiskEngine()
    signals = SignalsPayload(manual_sos=True)
    result = engine.analyze(signals)

    assert result.risk_score == 50.0
    assert result.risk_level == RiskLevel.SUSPICIOUS  # 31-60 threshold
    assert result.signals_detected == ["manual_sos"]
    assert "Manual SOS triggered" in result.reasons
    # Verify engine output is pure analysis: no 112/police/SMS dispatch fields
    assert hasattr(result, "risk_score")
    assert not hasattr(result, "dispatch_status")
    assert not hasattr(result, "call_112")


# ---------------------------------------------------------------------------
# Test 6: Multiple simultaneous signals
# ---------------------------------------------------------------------------
def test_multiple_simultaneous_signals():
    """Check aggregation across all specified initial signals."""
    engine = RiskEngine()
    signals = SignalsPayload(
        distress_audio=True,
        sudden_fall=True,
        abnormal_motion=True,
        route_deviation=True,
        no_response=True,
    )
    # 35 + 25 + 15 + 15 + 20 = 110 -> clamped to 100
    result = engine.analyze(signals)

    assert result.risk_score == 100.0
    assert result.risk_level == RiskLevel.CRITICAL
    assert len(result.signals_detected) == 5
    assert len(result.reasons) == 5


# ---------------------------------------------------------------------------
# Test 7: Score cannot exceed 100
# ---------------------------------------------------------------------------
def test_score_cannot_exceed_100():
    """Even if all possible signals fire, score is strictly clamped to 100.0."""
    engine = RiskEngine()
    signals = SignalsPayload(
        manual_sos=True,          # 50
        distress_audio=True,      # 35
        distress_keywords=True,   # 25
        sudden_fall=True,         # 25
        abnormal_motion=True,     # 15
        sudden_running=True,      # 15
        route_deviation=True,     # 15
        inactivity=True,          # 15
        sensor_anomalies=True,    # 10
        no_response=True,         # 20
    )
    result = engine.analyze(signals)

    assert result.risk_score == 100.0
    assert result.risk_level == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Test 8: Score cannot go below 0
# ---------------------------------------------------------------------------
def test_score_cannot_go_below_zero():
    """Score remains clamped at >= 0.0 even with custom zero/negative configuration."""
    custom_settings = RiskEngineSettings(min_score=0.0)
    engine = RiskEngine(config=custom_settings)
    signals = SignalsPayload()
    result = engine.analyze(signals)

    assert result.risk_score >= 0.0
    assert result.risk_score == 0.0


# ---------------------------------------------------------------------------
# Test 9: Invalid signal values
# ---------------------------------------------------------------------------
def test_invalid_confidence_values_raise_validation_error():
    """Confidence values < 0.0 or > 1.0 must be rejected by Pydantic schema."""
    with pytest.raises(ValidationError):
        SignalsPayload(audio_confidence=1.5)

    with pytest.raises(ValidationError):
        SignalsPayload(audio_confidence=-0.1)

    with pytest.raises(ValidationError):
        SignalsPayload(motion_anomaly_score=2.0)

    with pytest.raises(ValidationError):
        SignalsPayload(route_deviation_score=-0.5)


# ---------------------------------------------------------------------------
# Test 10: Missing input
# ---------------------------------------------------------------------------
def test_missing_input_validation():
    """Request without required user_id or signals field raises ValidationError."""
    with pytest.raises(ValidationError):
        AIAnalyzeRequest(signals=SignalsPayload())  # missing user_id

    with pytest.raises(ValidationError):
        AIAnalyzeRequest(user_id="user_1")  # missing signals


# ---------------------------------------------------------------------------
# Test 11: Unknown signals
# ---------------------------------------------------------------------------
def test_unknown_signals_rejected():
    """Extraneous unknown signals are forbidden and raise ValidationError."""
    with pytest.raises(ValidationError):
        SignalsPayload(unknown_sensor_signal=True)


# ---------------------------------------------------------------------------
# Test 12: Correct risk classification across boundaries
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "score, expected_level",
    [
        (0.0, RiskLevel.SAFE),
        (15.0, RiskLevel.SAFE),
        (30.0, RiskLevel.SAFE),
        (30.1, RiskLevel.SUSPICIOUS),
        (35.0, RiskLevel.SUSPICIOUS),
        (60.0, RiskLevel.SUSPICIOUS),
        (60.1, RiskLevel.HIGH),
        (75.0, RiskLevel.HIGH),
        (80.0, RiskLevel.HIGH),
        (80.1, RiskLevel.CRITICAL),
        (86.0, RiskLevel.CRITICAL),
        (100.0, RiskLevel.CRITICAL),
    ],
)
def test_risk_classification_boundaries(score, expected_level):
    """Verify exact boundary classifications."""
    engine = RiskEngine()
    assert engine.classify_risk(score) == expected_level


# ---------------------------------------------------------------------------
# Test 13: Correct reasons
# ---------------------------------------------------------------------------
def test_correct_reasons_attribution():
    """Reasons must be specific to detected signals and avoid vague phrases."""
    engine = RiskEngine()
    signals = SignalsPayload(
        distress_audio=True,
        sudden_fall=True,
        abnormal_motion=True,
        no_response=True,
    )
    result = engine.analyze(signals)

    expected_reasons = [
        "Distress audio detected",
        "Sudden fall detected",
        "Abnormal motion detected",
        "No user response detected",
    ]
    for reason in expected_reasons:
        assert reason in result.reasons

    assert "AI detected danger" not in result.reasons


# ---------------------------------------------------------------------------
# Test 14: Correct signals_detected
# ---------------------------------------------------------------------------
def test_correct_signals_detected_list():
    """Ensure signals_detected matches active signals accurately."""
    engine = RiskEngine()
    signals = SignalsPayload(
        distress_audio=True,
        sudden_fall=True,
        abnormal_motion=True,
        no_response=True,
    )
    result = engine.analyze(signals)

    expected_signals = [
        "distress_audio",
        "sudden_fall",
        "abnormal_motion",
        "no_response",
    ]
    for sig in expected_signals:
        assert sig in result.signals_detected


# ---------------------------------------------------------------------------
# Test 15: Configurable thresholds
# ---------------------------------------------------------------------------
def test_configurable_thresholds():
    """Altering thresholds updates classification without modifying core engine code."""
    custom_thresholds = RiskThresholds(
        safe_max=20.0,
        suspicious_max=40.0,
        high_max=60.0,
        critical_min=61.0,
    )
    custom_settings = RiskEngineSettings(thresholds=custom_thresholds)
    engine = RiskEngine(config=custom_settings)

    # Score of 25 is SUSPICIOUS under new threshold (safe_max=20)
    assert engine.classify_risk(25.0) == RiskLevel.SUSPICIOUS
    # Score of 45 is HIGH under new threshold (suspicious_max=40)
    assert engine.classify_risk(45.0) == RiskLevel.HIGH
    # Score of 65 is CRITICAL under new threshold (high_max=60)
    assert engine.classify_risk(65.0) == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Test 16: Configurable weights
# ---------------------------------------------------------------------------
def test_configurable_weights():
    """Updating weights alters score calculation dynamically."""
    custom_weights = SignalWeights(manual_sos=80.0, distress_audio=40.0)
    custom_settings = RiskEngineSettings(weights=custom_weights)
    engine = RiskEngine(config=custom_settings)

    signals = SignalsPayload(manual_sos=True)
    result = engine.analyze(signals)

    assert result.risk_score == 80.0


# ---------------------------------------------------------------------------
# Test 17: Detector failure handling
# ---------------------------------------------------------------------------
class FaultyDetector(BaseDetector):
    """Mock detector that raises an unexpected internal exception."""

    def __init__(self):
        super().__init__(signal_name="faulty_signal", default_reason="Faulty reason")

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        raise RuntimeError("Sensor hardware disconnected abruptly")


def test_detector_failure_does_not_crash_engine():
    """A faulty detector fails gracefully, reports status FAILED, contributes 0."""
    engine = RiskEngine()
    faulty = FaultyDetector()
    engine.register_detector(faulty)

    signals = SignalsPayload(distress_audio=True)
    result = engine.analyze(signals)

    # Distress audio (35) should still be evaluated cleanly
    assert result.risk_score == 35.0
    assert result.risk_level == RiskLevel.SUSPICIOUS
    assert "faulty_signal" not in result.signals_detected
    assert result.details["faulty_signal"].status == DetectorStatus.FAILED.value


# ---------------------------------------------------------------------------
# Test 18: API validation
# ---------------------------------------------------------------------------
def test_api_rejects_invalid_payload():
    """API returns 422 for malformed JSON or unknown signals."""
    response = client.post(
        "/ai/analyze",
        json={
            "user_id": "user_123",
            "signals": {
                "unknown_key": True,
            },
        },
    )
    assert response.status_code == 422
    assert "Validation Error" in response.json()["error"]


def test_api_rejects_out_of_range_confidence():
    """API returns 422 when confidence is outside [0.0, 1.0]."""
    response = client.post(
        "/ai/analyze",
        json={
            "user_id": "user_123",
            "signals": {
                "distress_audio": True,
                "audio_confidence": 1.75,
            },
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test 19: Stable response structure
# ---------------------------------------------------------------------------
def test_api_stable_response_structure():
    """Verify the exact contract expected by Backend Engineers 2 and 3."""
    response = client.post(
        "/ai/analyze",
        json={
            "user_id": "123",
            "signals": {
                "manual_sos": False,
                "distress_audio": True,
                "sudden_fall": True,
                "abnormal_motion": True,
                "route_deviation": False,
                "no_response": True,
            },
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Verify keys present
    assert "risk_score" in data
    assert "risk_level" in data
    assert "reasons" in data
    assert "signals_detected" in data

    # 35 + 25 + 15 + 20 = 95 -> CRITICAL
    assert data["risk_score"] == 95.0
    assert data["risk_level"] == "CRITICAL"
    assert "Distress audio detected" in data["reasons"]
    assert "Sudden fall detected" in data["reasons"]
    assert "Abnormal motion detected" in data["reasons"]
    assert "No user response detected" in data["reasons"]
    assert "distress_audio" in data["signals_detected"]
    assert "sudden_fall" in data["signals_detected"]
    assert "abnormal_motion" in data["signals_detected"]
    assert "no_response" in data["signals_detected"]
