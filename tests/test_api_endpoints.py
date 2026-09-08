"""Integration tests for FastAPI endpoints and concurrent requests.

Verifies HTTP status codes, routing aliases, error payloads, and thread-safety
under concurrent client interactions.
"""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from src.ai_engine.api import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data


def test_config_endpoint():
    response = client.get("/ai/config")
    assert response.status_code == 200
    data = response.json()

    assert "weights" in data
    assert "thresholds" in data
    assert "score_bounds" in data

    # Verify initial weights in config response
    assert data["weights"]["manual_sos"] == 50.0
    assert data["weights"]["distress_audio"] == 35.0
    assert data["thresholds"]["safe_max"] == 30.0
    assert data["thresholds"]["critical_min"] == 81.0


def test_api_v1_alias_endpoint():
    payload = {
        "user_id": "test_user_v1",
        "signals": {
            "manual_sos": True,
        },
    }
    resp = client.post("/api/v1/ai/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_score"] == 50.0
    assert data["risk_level"] == "SUSPICIOUS"


def test_validation_error_response_structure():
    payload = {
        "user_id": "usr_99",
        "signals": {
            "audio_confidence": 2.5,
        },
    }
    resp = client.post("/ai/analyze", json=payload)
    assert resp.status_code == 422
    data = resp.json()

    assert data["error"] == "Validation Error"
    assert "details" in data
    assert isinstance(data["details"], list)
    assert len(data["details"]) > 0
    assert "field" in data["details"][0]
    assert "message" in data["details"][0]


def test_concurrent_api_requests():
    """Simulate 20 concurrent requests to ensure thread safety and no state leaks."""
    scenarios = [
        ({"manual_sos": True}, 50.0, "SUSPICIOUS"),
        ({"route_deviation": True}, 15.0, "SAFE"),
        ({"distress_audio": True, "sudden_fall": True}, 60.0, "SUSPICIOUS"),
        ({"manual_sos": True, "distress_audio": True}, 85.0, "CRITICAL"),
        ({}, 0.0, "SAFE"),
    ] * 4  # 20 requests

    def send_request(idx_and_scenario):
        idx, (signals, expected_score, expected_level) = idx_and_scenario
        resp = client.post(
            "/ai/analyze",
            json={
                "user_id": f"concurrent_user_{idx}",
                "signals": signals,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_score"] == expected_score
        assert data["risk_level"] == expected_level

    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(send_request, enumerate(scenarios)))
