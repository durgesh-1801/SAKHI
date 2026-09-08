def test_journey_lifecycle_planned_to_completed(client, user_a_headers):
    # 1. Create planned journey
    create_payload = {
        "origin": "Tech Park Block 4",
        "destination": "Greenwood Residence",
        "expected_duration": 40,
        "auto_start": False
    }
    create_res = client.post("/api/v1/journeys", json=create_payload, headers=user_a_headers)
    assert create_res.status_code == 201
    j_data = create_res.json()
    assert j_data["status"] == "PLANNED"
    assert j_data["started_at"] is None
    j_id = j_data["id"]

    # 2. Start journey
    start_res = client.post(f"/api/v1/journeys/{j_id}/start", headers=user_a_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "ACTIVE"
    assert start_res.json()["started_at"] is not None

    # 3. Check active journey
    active_res = client.get("/api/v1/journeys/active", headers=user_a_headers)
    assert active_res.status_code == 200
    assert active_res.json()["id"] == j_id

    # 4. End journey
    end_res = client.post(f"/api/v1/journeys/{j_id}/end", headers=user_a_headers)
    assert end_res.status_code == 200
    assert end_res.json()["status"] == "COMPLETED"
    assert end_res.json()["ended_at"] is not None

    # 5. Active journey should now be None
    active_res2 = client.get("/api/v1/journeys/active", headers=user_a_headers)
    assert active_res2.status_code == 200
    assert active_res2.json() is None


def test_single_active_journey_constraint(client, user_a_headers):
    # Start journey 1
    j1_res = client.post(
        "/api/v1/journeys",
        json={"origin": "Origin A", "destination": "Destination B", "expected_duration": 30, "auto_start": True},
        headers=user_a_headers
    )
    assert j1_res.status_code == 201
    j1 = j1_res.json()
    assert j1["status"] == "ACTIVE"

    # Attempt to auto-start journey 2 while journey 1 is active -> 409 Conflict
    res2 = client.post(
        "/api/v1/journeys",
        json={"origin": "Origin C", "destination": "Destination D", "expected_duration": 20, "auto_start": True},
        headers=user_a_headers
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "CONFLICT"

    # Attempt to start a planned journey while journey 1 is active -> 409 Conflict
    j3 = client.post(
        "/api/v1/journeys",
        json={"origin": "Origin E", "destination": "Destination F", "expected_duration": 20, "auto_start": False},
        headers=user_a_headers
    ).json()
    res3 = client.post(f"/api/v1/journeys/{j3['id']}/start", headers=user_a_headers)
    assert res3.status_code == 409


def test_journey_cancellation_and_terminal_states(client, user_a_headers):
    j = client.post(
        "/api/v1/journeys",
        json={"origin": "Office", "destination": "Home", "expected_duration": 25, "auto_start": False},
        headers=user_a_headers
    ).json()

    # Cancel
    res_cancel = client.post(f"/api/v1/journeys/{j['id']}/cancel", headers=user_a_headers)
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    # Cannot start cancelled journey
    res_start = client.post(f"/api/v1/journeys/{j['id']}/start", headers=user_a_headers)
    assert res_start.status_code == 400

    # Cannot update cancelled journey
    res_update = client.put(f"/api/v1/journeys/{j['id']}", json={"origin": "Somewhere Else"}, headers=user_a_headers)
    assert res_update.status_code == 400


def test_journey_ownership_isolation(client, user_a_headers, user_b_headers):
    # User A creates a journey
    j_a = client.post(
        "/api/v1/journeys",
        json={"origin": "Secret Origin", "destination": "Secret Destination", "expected_duration": 60},
        headers=user_a_headers
    ).json()

    # User B cannot view User A's journey
    res_get = client.get(f"/api/v1/journeys/{j_a['id']}", headers=user_b_headers)
    assert res_get.status_code == 403

    # User B cannot start User A's journey
    res_start = client.post(f"/api/v1/journeys/{j_a['id']}/start", headers=user_b_headers)
    assert res_start.status_code == 403

    # User B cannot end User A's journey
    res_end = client.post(f"/api/v1/journeys/{j_a['id']}/end", headers=user_b_headers)
    assert res_end.status_code == 403

    # User B cannot cancel User A's journey
    res_cancel = client.post(f"/api/v1/journeys/{j_a['id']}/cancel", headers=user_b_headers)
    assert res_cancel.status_code == 403


def test_cannot_end_planned_or_cancelled_journey(client, user_a_headers):
    # 1. Planned journey cannot be ended before starting
    j_planned = client.post(
        "/api/v1/journeys",
        json={"origin": "Start Place", "destination": "End Place", "expected_duration": 15, "auto_start": False},
        headers=user_a_headers
    ).json()

    res_end_planned = client.post(f"/api/v1/journeys/{j_planned['id']}/end", headers=user_a_headers)
    assert res_end_planned.status_code == 400
    assert "not started" in res_end_planned.json()["error"]["message"]

    # 2. Cancel the planned journey
    client.post(f"/api/v1/journeys/{j_planned['id']}/cancel", headers=user_a_headers)

    # 3. Cancelled journey cannot be ended
    res_end_cancelled = client.post(f"/api/v1/journeys/{j_planned['id']}/end", headers=user_a_headers)
    assert res_end_cancelled.status_code == 400
    assert "cancelled" in res_end_cancelled.json()["error"]["message"]


def test_journey_location_whitespace_rejected(client, user_a_headers):
    bad_journey = {
        "origin": "   ",
        "destination": "Valid Destination",
        "expected_duration": 30
    }
    response = client.post("/api/v1/journeys", json=bad_journey, headers=user_a_headers)
    assert response.status_code == 422


def test_journey_idempotent_actions(client, user_a_headers):
    j = client.post(
        "/api/v1/journeys",
        json={"origin": "Station", "destination": "Airport", "expected_duration": 50, "auto_start": True},
        headers=user_a_headers
    ).json()

    # Re-starting an already active journey returns the active journey
    start_again = client.post(f"/api/v1/journeys/{j['id']}/start", headers=user_a_headers)
    assert start_again.status_code == 200
    assert start_again.json()["status"] == "ACTIVE"

    # End the journey
    end_once = client.post(f"/api/v1/journeys/{j['id']}/end", headers=user_a_headers)
    assert end_once.status_code == 200
    assert end_once.json()["status"] == "COMPLETED"

    # Re-ending an already completed journey is idempotent
    end_again = client.post(f"/api/v1/journeys/{j['id']}/end", headers=user_a_headers)
    assert end_again.status_code == 200
    assert end_again.json()["status"] == "COMPLETED"
