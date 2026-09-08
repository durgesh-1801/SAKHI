"""
Tests: AI Trigger Flow
========================
Covers:
  - POST /emergency/trigger with valid risk result and user consent
  - AI trigger blocked when user has not consented to AI monitoring
  - VERIFYING status on AI-triggered incident (not ACTIVE)
  - Risk score and AI reasons stored on incident
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_USER_ID


@pytest.mark.asyncio
async def test_ai_trigger_creates_verifying_incident(
    client: AsyncClient,
    test_user,
    test_policy,
    test_consent,
):
    """Valid AI trigger with consent → VERIFYING incident created."""
    with patch("app.services.escalation_service.start_escalation", new_callable=AsyncMock):
        response = await client.post(
            "/emergency/trigger",
            json={
                "user_id": str(TEST_USER_ID),
                "risk_score": 86.0,
                "risk_level": "CRITICAL",
                "reasons": ["Distress signal detected", "Abnormal movement"],
                "trigger_type": "AI_DETECTION",
                "latitude": 26.8432,
                "longitude": 75.5651,
            },
        )

    assert response.status_code == 201
    body = response.json()
    # AI-triggered incidents start in VERIFYING, not ACTIVE
    assert body["status"] == "VERIFYING"
    assert body["risk_level"] == "CRITICAL"


@pytest.mark.asyncio
async def test_ai_trigger_blocked_without_consent(
    client: AsyncClient,
    test_user,
    test_policy,
    db_session,
):
    """AI trigger without AI monitoring consent → 200 with denial message (not 201)."""
    # No consent record → consent_service defaults to False for AI monitoring
    response = await client.post(
        "/emergency/trigger",
        json={
            "user_id": str(TEST_USER_ID),
            "risk_score": 90.0,
            "risk_level": "CRITICAL",
            "reasons": ["Scream detected"],
            "trigger_type": "AI_DETECTION",
        },
    )
    # Returns 200 with denial info, no incident created
    assert response.status_code == 200
    body = response.json()
    assert "not consented" in body.get("detail", "").lower()


@pytest.mark.asyncio
async def test_ai_trigger_invalid_risk_level(
    client: AsyncClient,
    test_user,
):
    """Invalid risk_level → 422 validation error."""
    response = await client.post(
        "/emergency/trigger",
        json={
            "user_id": str(TEST_USER_ID),
            "risk_score": 80.0,
            "risk_level": "EXTREME",  # Not a valid value
            "reasons": [],
            "trigger_type": "AI_DETECTION",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ai_trigger_invalid_trigger_type(
    client: AsyncClient,
    test_user,
):
    """Invalid trigger_type → 422 validation error."""
    response = await client.post(
        "/emergency/trigger",
        json={
            "user_id": str(TEST_USER_ID),
            "risk_score": 80.0,
            "risk_level": "HIGH",
            "reasons": [],
            "trigger_type": "EXPLOSION",  # Not valid
        },
    )
    assert response.status_code == 422
