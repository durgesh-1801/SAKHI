def test_default_policy(client, user_a_headers):
    response = client.get("/api/v1/emergency-policy", headers=user_a_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["verification_timeout"] == 30
    assert data["auto_alert_enabled"] is True
    assert data["location_sharing_enabled"] is True
    assert data["primary_contact_id"] is None
    assert data["secondary_contact_id"] is None


def test_update_policy_with_valid_contacts(client, user_a_headers):
    # Create two contacts for User A
    c1 = client.post("/api/v1/contacts", json={"name": "C1", "phone": "+919800000001", "priority": 1}, headers=user_a_headers).json()
    c2 = client.post("/api/v1/contacts", json={"name": "C2", "phone": "+919800000002", "priority": 2}, headers=user_a_headers).json()

    policy_payload = {
        "verification_timeout": 45,
        "auto_alert_enabled": True,
        "location_sharing_enabled": True,
        "primary_contact_id": c1["id"],
        "secondary_contact_id": c2["id"],
        "escalation_level": 2
    }
    response = client.put("/api/v1/emergency-policy", json=policy_payload, headers=user_a_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["verification_timeout"] == 45
    assert data["primary_contact_id"] == c1["id"]
    assert data["secondary_contact_id"] == c2["id"]
    assert data["escalation_level"] == 2


def test_policy_rejects_nonexistent_contact(client, user_a_headers):
    payload = {
        "primary_contact_id": "00000000-0000-0000-0000-000000000000"
    }
    response = client.put("/api/v1/emergency-policy", json=payload, headers=user_a_headers)
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "does not exist" in data["error"]["message"]


def test_policy_rejects_cross_user_contact(client, user_a_headers, user_b_headers):
    # User B creates a contact
    contact_b = client.post(
        "/api/v1/contacts",
        json={"name": "User B Contact", "phone": "+919800000099", "priority": 1},
        headers=user_b_headers
    ).json()

    # User A attempts to set User B's contact as their primary emergency contact
    response = client.put(
        "/api/v1/emergency-policy",
        json={"primary_contact_id": contact_b["id"]},
        headers=user_a_headers
    )
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "does not belong to your account" in data["error"]["message"]


def test_policy_rejects_duplicate_primary_and_secondary(client, user_a_headers):
    c1 = client.post(
        "/api/v1/contacts",
        json={"name": "Sole Contact", "phone": "+919800000055", "priority": 1},
        headers=user_a_headers
    ).json()

    response = client.put(
        "/api/v1/emergency-policy",
        json={"primary_contact_id": c1["id"], "secondary_contact_id": c1["id"]},
        headers=user_a_headers
    )
    assert response.status_code == 400
    assert "distinct" in response.json()["error"]["message"]


def test_contact_deletion_unlinks_from_policy(client, user_a_headers):
    c1 = client.post("/api/v1/contacts", json={"name": "Target", "phone": "+919800000077", "priority": 1}, headers=user_a_headers).json()
    
    # Set as primary
    client.put("/api/v1/emergency-policy", json={"primary_contact_id": c1["id"]}, headers=user_a_headers)

    # Delete contact
    client.delete(f"/api/v1/contacts/{c1['id']}", headers=user_a_headers)

    # Check policy -> primary_contact_id should now be None
    policy = client.get("/api/v1/emergency-policy", headers=user_a_headers).json()
    assert policy["primary_contact_id"] is None
