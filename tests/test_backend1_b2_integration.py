"""Integration tests between Backend 1 (AI & Risk Engine) and Backend 2 (Core Backend & Data).

Tests consent enforcement, context retrieval, active journey correlation,
audio pipeline validation, and fail-safe error handling.
"""

import io

from fastapi.testclient import TestClient

from app.schemas.consent import ConsentUpdate
from app.schemas.journey import JourneyCreate
from app.services.consent_service import consent_service
from app.services.journey_service import journey_service


def test_ai_analyze_with_full_consent(client: TestClient, user_a, db_session):
    """When user grants all consents, signals are evaluated cleanly."""
    # Grant all consents
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True, location_monitoring=True),
    )

    payload = {
        "user_id": user_a.id,
        "signals": {
            "distress_audio": True,
            "sudden_fall": True,
        },
    }
    response = client.post("/api/v1/ai/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # 35 + 25 = 60 -> SUSPICIOUS
    assert data["risk_score"] == 60.0
    assert data["risk_level"] == "SUSPICIOUS"
    assert "distress_audio" in data["signals_detected"]
    assert "sudden_fall" in data["signals_detected"]


def test_rule1_ai_detection_disabled_aborts_inference(client: TestClient, user_a, db_session):
    """RULE 1: If ai_detection_permitted is False, safety inference is aborted with HTTP 403."""
    # Explicitly revoke AI detection consent
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=False),
    )

    payload = {
        "user_id": user_a.id,
        "signals": {
            "distress_audio": True,
            "sudden_fall": True,
        },
    }
    response = client.post("/api/v1/ai/analyze", json=payload)
    assert response.status_code == 403
    data = response.json()
    assert "AI_CONSENT_REVOKED" in str(data)


def test_rule2_audio_analysis_disabled_strips_audio_signals(client: TestClient, user_a, db_session):
    """RULE 2: If audio_analysis_permitted is False, audio distress signals are stripped."""
    # AI detection True, but audio analysis False
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=False, location_monitoring=True),
    )

    payload = {
        "user_id": user_a.id,
        "signals": {
            "distress_audio": True,      # Should be stripped
            "audio_confidence": 0.95,    # Should be stripped
            "sudden_fall": True,         # Permitted (+25)
        },
    }
    response = client.post("/api/v1/ai/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Only sudden fall (25.0) contributes; distress audio is stripped
    assert data["risk_score"] == 25.0
    assert data["risk_level"] == "SAFE"
    assert "distress_audio" not in data["signals_detected"]
    assert "sudden_fall" in data["signals_detected"]
    assert "Distress audio detected" not in data["reasons"]
    assert "Sudden fall detected" in data["reasons"]


def test_rule3_location_monitoring_disabled_strips_route_signals(client: TestClient, user_a, db_session):
    """RULE 3: If location_monitoring_permitted is False, route deviation signals are stripped."""
    # AI detection True, but location monitoring False
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True, location_monitoring=False),
    )

    payload = {
        "user_id": user_a.id,
        "signals": {
            "route_deviation": True,        # Should be stripped
            "route_deviation_score": 0.90,  # Should be stripped
            "abnormal_motion": True,        # Permitted (+15)
        },
    }
    response = client.post("/api/v1/ai/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Only abnormal motion (15.0) contributes; route deviation is stripped
    assert data["risk_score"] == 15.0
    assert data["risk_level"] == "SAFE"
    assert "route_deviation" not in data["signals_detected"]
    assert "abnormal_motion" in data["signals_detected"]


def test_active_safe_journey_correlation(client: TestClient, user_a, db_session):
    """When a Safe Journey is active, route deviation reasons correlate the journey."""
    # Grant consents
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, location_monitoring=True),
    )
    # Create an active Safe Journey
    journey_in = JourneyCreate(
        origin="Campus Gate 1",
        destination="Metro Station",
        expected_duration=25,
        auto_start=True,
    )
    journey_service.create_journey(db_session, user_a.id, journey_in)

    payload = {
        "user_id": user_a.id,
        "signals": {
            "route_deviation": True,
        },
    }
    response = client.post("/api/v1/ai/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["risk_score"] == 15.0
    assert "Significant route deviation during active Safe Journey" in data["reasons"]


def test_ai_analyze_missing_user_returns_404(client: TestClient):
    """Querying non-existent user returns HTTP 404."""
    payload = {
        "user_id": "non_existent_uuid_999",
        "signals": {},
    }
    response = client.post("/api/v1/ai/analyze", json=payload)
    assert response.status_code == 404


def test_audio_analyze_valid_file_and_consent(client: TestClient, user_a, db_session):
    """Uploading valid audio with consent extracts acoustic features and scores risk."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True),
    )

    # Generate synthetic high-amplitude audio bytes (screaming/loud struggle)
    sample_val = 25000  # High amplitude 16-bit PCM
    sample_bytes = sample_val.to_bytes(2, byteorder="little", signed=True) * 2000
    audio_file = io.BytesIO(sample_bytes)

    response = client.post(
        "/api/v1/ai/analyze-audio",
        data={"user_id": user_a.id, "sudden_fall": True},
        files={"file": ("struggle_recording.wav", audio_file, "audio/wav")},
    )
    assert response.status_code == 200
    data = response.json()

    # Distress audio (35) + fall (25) = 60 -> SUSPICIOUS
    assert data["risk_score"] == 60.0
    assert "distress_audio" in data["signals_detected"]
    assert "sudden_fall" in data["signals_detected"]


def test_audio_analyze_revoked_consent_returns_403(client: TestClient, user_a, db_session):
    """Uploading audio when audio consent is False returns HTTP 403."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=False),
    )

    audio_file = io.BytesIO(b"\x00\x00" * 100)
    response = client.post(
        "/api/v1/ai/analyze-audio",
        data={"user_id": user_a.id},
        files={"file": ("recording.wav", audio_file, "audio/wav")},
    )
    assert response.status_code == 403
    assert "AUDIO_ANALYSIS_NOT_PERMITTED" in str(response.json())


def test_audio_analyze_empty_file_returns_400(client: TestClient, user_a, db_session):
    """Uploading 0-byte audio file returns HTTP 400."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True),
    )

    empty_file = io.BytesIO(b"")
    response = client.post(
        "/api/v1/ai/analyze-audio",
        data={"user_id": user_a.id},
        files={"file": ("empty.wav", empty_file, "audio/wav")},
    )
    assert response.status_code == 400
    assert "EMPTY_AUDIO" in str(response.json())


def test_audio_analyze_unsupported_format_returns_415(client: TestClient, user_a, db_session):
    """Uploading unsupported format (.txt, .exe) returns HTTP 415."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True),
    )

    text_file = io.BytesIO(b"This is a text file, not audio")
    response = client.post(
        "/api/v1/ai/analyze-audio",
        data={"user_id": user_a.id},
        files={"file": ("document.txt", text_file, "text/plain")},
    )
    assert response.status_code == 415
    assert "UNSUPPORTED_AUDIO_FORMAT" in str(response.json())


def test_ai_config_endpoint(client: TestClient):
    """GET /api/v1/ai/config returns active engine weights and thresholds."""
    response = client.get("/api/v1/ai/config")
    assert response.status_code == 200
    data = response.json()
    assert data["weights"]["manual_sos"] == 50.0
    assert data["thresholds"]["safe_max"] == 30.0
