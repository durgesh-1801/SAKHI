"""Unit tests for schema validation and edge cases.

Validates input sanitization, type enforcement, extra-field rejection,
and serialization contracts for SAKHI API models.
"""

import pytest
from pydantic import ValidationError
from src.ai_engine.schemas import (
    SignalsPayload,
    AIAnalyzeRequest,
    AIAnalyzeResponse,
    RiskLevel,
    SignalDetail,
)


def test_signals_payload_defaults():
    payload = SignalsPayload()
    data = payload.model_dump()

    # All booleans should default to False
    assert data["manual_sos"] is False
    assert data["distress_audio"] is False
    assert data["distress_keywords"] is False
    assert data["sudden_fall"] is False
    assert data["abnormal_motion"] is False
    assert data["sudden_running"] is False
    assert data["route_deviation"] is False
    assert data["inactivity"] is False
    assert data["sensor_anomalies"] is False
    assert data["no_response"] is False

    # All confidence scores should default to None
    assert data["audio_confidence"] is None
    assert data["keyword_confidence"] is None
    assert data["fall_confidence"] is None
    assert data["motion_anomaly_score"] is None
    assert data["route_deviation_score"] is None


@pytest.mark.parametrize(
    "field, valid_value",
    [
        ("audio_confidence", 0.0),
        ("audio_confidence", 1.0),
        ("audio_confidence", 0.5),
        ("keyword_confidence", 0.0),
        ("keyword_confidence", 1.0),
        ("fall_confidence", 0.0),
        ("fall_confidence", 1.0),
        ("motion_anomaly_score", 0.0),
        ("motion_anomaly_score", 1.0),
        ("route_deviation_score", 0.0),
        ("route_deviation_score", 1.0),
    ],
)
def test_valid_confidence_boundaries(field, valid_value):
    payload = SignalsPayload(**{field: valid_value})
    assert getattr(payload, field) == valid_value


@pytest.mark.parametrize(
    "field, invalid_value",
    [
        ("audio_confidence", -0.01),
        ("audio_confidence", 1.01),
        ("keyword_confidence", -5.0),
        ("keyword_confidence", 10.0),
        ("fall_confidence", -1.0),
        ("fall_confidence", 2.0),
        ("motion_anomaly_score", -0.5),
        ("motion_anomaly_score", 1.5),
        ("route_deviation_score", -0.1),
        ("route_deviation_score", 1.1),
    ],
)
def test_invalid_confidence_boundaries(field, invalid_value):
    with pytest.raises(ValidationError):
        SignalsPayload(**{field: invalid_value})


def test_extra_fields_forbidden_in_signals():
    with pytest.raises(ValidationError) as exc:
        SignalsPayload(random_extra_field="malicious_payload")
    assert "extra_forbidden" in str(exc.value)


def test_extra_fields_forbidden_in_request():
    with pytest.raises(ValidationError) as exc:
        AIAnalyzeRequest(
            user_id="user_1",
            signals=SignalsPayload(),
            unexpected_field=123,
        )
    assert "extra_forbidden" in str(exc.value)


def test_user_id_min_length_validation():
    # Empty string should fail
    with pytest.raises(ValidationError):
        AIAnalyzeRequest(user_id="", signals=SignalsPayload())

    # Valid string succeeds
    req = AIAnalyzeRequest(user_id="u", signals=SignalsPayload())
    assert req.user_id == "u"


def test_response_model_serialization():
    resp = AIAnalyzeResponse(
        risk_score=75.5,
        risk_level=RiskLevel.HIGH,
        reasons=["Distress audio detected", "Sudden fall detected"],
        signals_detected=["distress_audio", "sudden_fall"],
        details={
            "distress_audio": SignalDetail(
                signal_name="distress_audio",
                detected=True,
                weight_contributed=35.0,
                confidence=0.9,
                reason="Distress audio detected",
                status="SUCCESS",
            )
        },
    )

    json_dict = resp.model_dump()
    assert json_dict["risk_score"] == 75.5
    assert json_dict["risk_level"] == "HIGH"
    assert len(json_dict["reasons"]) == 2
    assert len(json_dict["signals_detected"]) == 2
    assert "distress_audio" in json_dict["details"]
