def test_ai_risk_context_reflects_consent_and_journey(client, user_a, user_a_headers):
    # Initial state: AI detection is disabled by default
    res = client.get(f"/api/v1/context/ai-risk/{user_a.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["ai_detection_permitted"] is False
    assert data["audio_analysis_permitted"] is False
    assert data["active_journey"] is None

    # Enable AI detection & Audio analysis via consent
    client.put(
        "/api/v1/consent",
        json={"ai_detection": True, "audio_analysis": True, "location_monitoring": True},
        headers=user_a_headers
    )

    # Start an active journey
    client.post(
        "/api/v1/journeys",
        json={"origin": "Campus", "destination": "Hostel", "expected_duration": 15, "auto_start": True},
        headers=user_a_headers
    )

    # Query context again
    res2 = client.get(f"/api/v1/context/ai-risk/{user_a.id}")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["ai_detection_permitted"] is True
    assert data2["audio_analysis_permitted"] is True
    assert data2["location_monitoring_permitted"] is True
    assert data2["active_journey"] is not None
    assert data2["active_journey"]["origin"] == "Campus"
    assert data2["active_journey"]["destination"] == "Hostel"


def test_emergency_dispatch_context_reflects_policy_and_contacts(client, user_a, user_a_headers):
    # 1. Add contacts with priorities
    client.post("/api/v1/contacts", json={"name": "Guardian 1", "phone": "+919900112233", "priority": 1}, headers=user_a_headers)
    client.post("/api/v1/contacts", json={"name": "Guardian 2", "phone": "+919900112244", "priority": 2}, headers=user_a_headers)

    # 2. Configure consent: Enable automatic escalation, but leave location_monitoring false
    client.put(
        "/api/v1/consent",
        json={"automatic_escalation": True, "location_monitoring": False},
        headers=user_a_headers
    )

    # 3. Query emergency dispatch context (Backend 3 contract)
    res = client.get(f"/api/v1/context/emergency-dispatch/{user_a.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == user_a.id
    assert data["user_name"] == user_a.name
    assert data["auto_escalation_permitted"] is True
    # Crucial consent override check: even though policy default has location_sharing_enabled=True,
    # because user consent has location_monitoring=False, effective location_sharing_enabled is False!
    assert data["location_sharing_enabled"] is False
    assert len(data["recipients"]) == 2
    assert data["recipients"][0]["priority"] == 1


def test_my_safety_profile_authenticated(client, user_a, user_a_headers):
    res = client.get("/api/v1/context/my-safety-profile", headers=user_a_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == user_a.id
    assert "policy" in data
    assert "consent" in data


def test_context_endpoints_reject_nonexistent_user(client):
    ghost_id = "00000000-0000-0000-0000-000000000000"
    res_ai = client.get(f"/api/v1/context/ai-risk/{ghost_id}")
    assert res_ai.status_code == 404
    assert res_ai.json()["error"]["code"] == "NOT_FOUND"

    res_dispatch = client.get(f"/api/v1/context/emergency-dispatch/{ghost_id}")
    assert res_dispatch.status_code == 404
    assert res_dispatch.json()["error"]["code"] == "NOT_FOUND"
