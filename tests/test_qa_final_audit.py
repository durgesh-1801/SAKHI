"""Deep QA & Release Validation Test Suite for SAKHI AI / Risk Engine.

Comprehensive adversarial, boundary, security, fuzzing, concurrency,
performance, and OpenAPI compliance tests.
"""

import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.ai_engine.api import app
from src.ai_engine.config import RiskThresholds, SignalWeights
from src.ai_engine.engine import RiskEngine
from src.ai_engine.schemas import RiskLevel, SignalsPayload

client = TestClient(app)


# ===========================================================================
# 1. SECURITY HEADERS & CORS
# ===========================================================================
def test_security_headers_present():
    """Verify security headers are applied to HTTP responses."""
    response = client.get("/health")
    assert response.status_code == 200
    headers = response.headers

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert "strict-transport-security" in headers


def test_cors_preflight_and_origin():
    """Verify CORS headers respond to cross-origin requests."""
    response = client.options(
        "/ai/analyze",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in ["*", "http://localhost:3000"]


# ===========================================================================
# 2. ADVERSARIAL INPUTS & FUZZING
# ===========================================================================
def test_fuzz_sql_injection_in_user_id():
    """Ensure SQL injection strings in user_id do not trigger 500 or execution."""
    sql_payload = "'; DROP TABLE users; --"
    res = client.post(
        "/ai/analyze",
        json={"user_id": sql_payload, "signals": {"manual_sos": True}},
    )
    assert res.status_code == 200
    assert res.json()["risk_score"] == 50.0


def test_fuzz_xss_payload_in_user_id():
    """Ensure script injection strings in user_id are safely handled."""
    xss_payload = "<script>alert('pwned')</script>"
    res = client.post(
        "/ai/analyze",
        json={"user_id": xss_payload, "signals": {}},
    )
    assert res.status_code == 200
    assert res.json()["risk_score"] == 0.0


def test_fuzz_unicode_and_emojis_in_user_id():
    """Ensure multilingual unicode and emojis in user_id are safely handled."""
    unicode_user = "user_🇮🇳_सखी_सुरक्षा_999"
    res = client.post(
        "/ai/analyze",
        json={"user_id": unicode_user, "signals": {"route_deviation": True}},
    )
    assert res.status_code == 200
    assert res.json()["risk_score"] == 15.0


def test_reject_whitespace_only_user_id():
    """Whitespace-only user_id must be rejected with HTTP 422."""
    res = client.post(
        "/ai/analyze",
        json={"user_id": "    \t \n  ", "signals": {}},
    )
    assert res.status_code == 422
    assert res.json()["error"] == "Validation Error"


def test_reject_oversized_user_id():
    """User IDs exceeding 256 characters must be rejected with HTTP 422."""
    giant_user_id = "u" * 257
    res = client.post(
        "/ai/analyze",
        json={"user_id": giant_user_id, "signals": {}},
    )
    assert res.status_code == 422


@pytest.mark.parametrize(
    "invalid_signals_type",
    [
        "just a string",
        12345,
        ["list", "of", "items"],
        None,
    ],
)
def test_fuzz_invalid_signals_types(invalid_signals_type):
    """Signals must be a valid JSON object, otherwise reject with 422."""
    res = client.post(
        "/ai/analyze",
        json={"user_id": "usr_test", "signals": invalid_signals_type},
    )
    assert res.status_code == 422


def test_fuzz_massive_unknown_fields():
    """Rejects payloads flooded with hundreds of arbitrary unknown fields."""
    flood_signals = {f"malicious_field_{i}": True for i in range(200)}
    res = client.post(
        "/ai/analyze",
        json={"user_id": "usr_test", "signals": flood_signals},
    )
    assert res.status_code == 422


# ===========================================================================
# 3. AI COMBINATION MATRIX TESTING
# ===========================================================================
@pytest.mark.parametrize(
    "signal_name, expected_weight, expected_level, expected_reason",
    [
        ("manual_sos", 50.0, RiskLevel.SUSPICIOUS, "Manual SOS triggered"),
        ("distress_audio", 35.0, RiskLevel.SUSPICIOUS, "Distress audio detected"),
        ("distress_keywords", 25.0, RiskLevel.SAFE, "Distress keywords detected"),
        ("sudden_fall", 25.0, RiskLevel.SAFE, "Sudden fall detected"),
        ("abnormal_motion", 15.0, RiskLevel.SAFE, "Abnormal motion detected"),
        ("sudden_running", 15.0, RiskLevel.SAFE, "Sudden running detected"),
        ("route_deviation", 15.0, RiskLevel.SAFE, "Route deviation detected"),
        ("inactivity", 15.0, RiskLevel.SAFE, "Unusual inactivity detected"),
        ("sensor_anomalies", 10.0, RiskLevel.SAFE, "Sensor anomalies detected"),
        ("no_response", 20.0, RiskLevel.SAFE, "No user response detected"),
    ],
)
def test_every_single_signal_in_isolation(signal_name, expected_weight, expected_level, expected_reason):
    """Verify every single signal alone produces exact weight, level, and reason."""
    engine = RiskEngine()
    payload = SignalsPayload(**{signal_name: True})
    res = engine.analyze(payload)

    assert res.risk_score == expected_weight
    assert res.risk_level == expected_level
    assert res.signals_detected == [signal_name]
    assert res.reasons == [expected_reason]


def test_pairwise_combinations():
    """Verify curated pairwise safety signal interactions."""
    engine = RiskEngine()

    # manual_sos (50) + sudden_fall (25) = 75 -> HIGH
    p1 = engine.analyze(SignalsPayload(manual_sos=True, sudden_fall=True))
    assert p1.risk_score == 75.0
    assert p1.risk_level == RiskLevel.HIGH
    assert set(p1.signals_detected) == {"manual_sos", "sudden_fall"}

    # sudden_running (15) + abnormal_motion (15) = 30 -> SAFE boundary
    p2 = engine.analyze(SignalsPayload(sudden_running=True, abnormal_motion=True))
    assert p2.risk_score == 30.0
    assert p2.risk_level == RiskLevel.SAFE

    # inactivity (15) + no_response (20) = 35 -> SUSPICIOUS
    p3 = engine.analyze(SignalsPayload(inactivity=True, no_response=True))
    assert p3.risk_score == 35.0
    assert p3.risk_level == RiskLevel.SUSPICIOUS

    # sensor_anomalies (10) + route_deviation (15) = 25 -> SAFE
    p4 = engine.analyze(SignalsPayload(sensor_anomalies=True, route_deviation=True))
    assert p4.risk_score == 25.0
    assert p4.risk_level == RiskLevel.SAFE


def test_no_duplicate_reasons_or_signals():
    """Verify reasons and detected signals contain no duplicates."""
    engine = RiskEngine()
    signals = SignalsPayload(
        manual_sos=True,
        distress_audio=True,
        audio_confidence=0.99,  # both flag and confidence active
    )
    res = engine.analyze(signals)

    assert len(res.signals_detected) == len(set(res.signals_detected))
    assert len(res.reasons) == len(set(res.reasons))


# ===========================================================================
# 4. CONFIGURATION HARDENING & VALIDATION
# ===========================================================================
def test_reject_negative_signal_weights():
    """Negative weights must be rejected by SignalWeights validator."""
    with pytest.raises(ValidationError):
        SignalWeights(manual_sos=-10.0)

    with pytest.raises(ValidationError):
        SignalWeights(distress_audio=-0.01)


def test_reject_inverted_thresholds():
    """Inverted threshold order must be rejected."""
    with pytest.raises(ValidationError):
        RiskThresholds(safe_max=70.0, suspicious_max=50.0)

    with pytest.raises(ValidationError):
        RiskThresholds(high_max=95.0, critical_min=90.0)


def test_engine_rejects_invalid_dynamic_thresholds():
    """RiskEngine.update_thresholds rejects invalid threshold order."""
    engine = RiskEngine()
    with pytest.raises(ValidationError):
        engine.update_thresholds(safe_max=90.0, suspicious_max=40.0)


# ===========================================================================
# 5. IDEMPOTENCY & DETERMINISM
# ===========================================================================
def test_idempotency_over_repeated_calls():
    """Ensure identical inputs generate bit-for-bit identical outputs 50 times."""
    payload = {
        "user_id": "idempotent_user",
        "signals": {
            "distress_audio": True,
            "sudden_fall": True,
            "abnormal_motion": True,
        },
    }
    first_res = client.post("/ai/analyze", json=payload).json()

    for _ in range(50):
        subsequent_res = client.post("/ai/analyze", json=payload).json()
        assert subsequent_res == first_res


# ===========================================================================
# 6. OPENAPI DOCUMENTATION COMPLIANCE
# ===========================================================================
def test_openapi_schema_endpoint():
    """Verify OpenAPI schema is generated properly with all routes documented."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()

    assert schema["info"]["title"] == "SAKHI AI Risk Engine"
    assert "/ai/analyze" in schema["paths"]
    assert "/health" in schema["paths"]
    assert "/ai/config" in schema["paths"]

    # Verify analyze response schema
    analyze_post = schema["paths"]["/ai/analyze"]["post"]
    assert "200" in analyze_post["responses"]


# ===========================================================================
# 7. PERFORMANCE SANITY CHECK
# ===========================================================================
def test_performance_latency_sanity():
    """100 sequential requests must execute in under 1 second locally (<10ms/req)."""
    payload = {
        "user_id": "perf_user",
        "signals": {
            "distress_audio": True,
            "sudden_fall": True,
        },
    }
    start = time.perf_counter()
    for _ in range(100):
        res = client.post("/ai/analyze", json=payload)
        assert res.status_code == 200
    duration = time.perf_counter() - start

    assert duration < 1.0, f"Expected 100 requests in <1.0s, took {duration:.2f}s"


# ===========================================================================
# 8. EMERGENCY BOUNDARY SANITY
# ===========================================================================
def test_emergency_boundary_no_dispatch_side_effects():
    """Strict check that response contains no emergency dispatch triggers."""
    res = client.post(
        "/ai/analyze",
        json={"user_id": "boundary_user", "signals": {"manual_sos": True}},
    )
    assert res.status_code == 200
    data = res.json()

    # Only safe analysis fields allowed
    forbidden_keys = {
        "dispatch", "call_112", "police", "sms", "notify_guardian",
        "emergency_escalation", "location_tracking", "fir_id",
    }
    for key in forbidden_keys:
        assert key not in data
