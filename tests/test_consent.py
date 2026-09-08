def test_default_consent_is_opt_in(client, user_a_headers):
    response = client.get("/api/v1/consent", headers=user_a_headers)
    assert response.status_code == 200
    data = response.json()
    # In SAKHI, consent is opt-in by default
    assert data["location_monitoring"] is False
    assert data["ai_detection"] is False
    assert data["audio_analysis"] is False
    assert data["automatic_escalation"] is False
    assert data["evidence_collection"] is False


def test_update_consent_settings(client, user_a_headers):
    update_payload = {
        "location_monitoring": True,
        "ai_detection": True,
        "automatic_escalation": True
    }
    response = client.put("/api/v1/consent", json=update_payload, headers=user_a_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["location_monitoring"] is True
    assert data["ai_detection"] is True
    assert data["audio_analysis"] is False  # Left untouched
    assert data["automatic_escalation"] is True
    assert data["evidence_collection"] is False


def test_consent_user_isolation(client, user_a_headers, user_b_headers):
    # User A enables AI detection
    client.put("/api/v1/consent", json={"ai_detection": True}, headers=user_a_headers)

    # User B checks their consent -> still False
    res_b = client.get("/api/v1/consent", headers=user_b_headers)
    assert res_b.status_code == 200
    assert res_b.json()["ai_detection"] is False
