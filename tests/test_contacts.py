def test_create_and_list_contacts(client, user_a_headers):
    # Add first contact
    contact_1 = {
        "name": "Mom",
        "phone": "+919811122233",
        "relationship_type": "Mother",
        "priority": 1,
        "verified": True
    }
    res1 = client.post("/api/v1/contacts", json=contact_1, headers=user_a_headers)
    assert res1.status_code == 201
    c1_id = res1.json()["id"]

    # Add second contact
    contact_2 = {
        "name": "Kavita Friend",
        "phone": "+919844455566",
        "relationship_type": "Friend",
        "priority": 2,
        "verified": False
    }
    res2 = client.post("/api/v1/contacts", json=contact_2, headers=user_a_headers)
    assert res2.status_code == 201

    # List contacts
    list_res = client.get("/api/v1/contacts", headers=user_a_headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 2
    assert items[0]["name"] == "Mom"
    assert items[0]["priority"] == 1
    assert items[1]["name"] == "Kavita Friend"
    assert items[1]["priority"] == 2


def test_update_and_delete_contact(client, user_a_headers):
    # Create contact
    contact = {
        "name": "Rohan",
        "phone": "+919877788899",
        "relationship_type": "Brother",
        "priority": 3
    }
    create_res = client.post("/api/v1/contacts", json=contact, headers=user_a_headers)
    c_id = create_res.json()["id"]

    # Update contact
    update_res = client.put(
        f"/api/v1/contacts/{c_id}",
        json={"priority": 1, "relationship_type": "Brother & Guardian"},
        headers=user_a_headers
    )
    assert update_res.status_code == 200
    assert update_res.json()["priority"] == 1
    assert update_res.json()["relationship_type"] == "Brother & Guardian"

    # Delete contact
    delete_res = client.delete(f"/api/v1/contacts/{c_id}", headers=user_a_headers)
    assert delete_res.status_code == 200

    # Verify deleted
    get_res = client.get(f"/api/v1/contacts/{c_id}", headers=user_a_headers)
    assert get_res.status_code == 404


def test_contact_ownership_isolation(client, user_a_headers, user_b_headers):
    # User A creates a contact
    contact_a = {
        "name": "User A Private Contact",
        "phone": "+919100010001",
        "relationship_type": "Confidant",
        "priority": 1
    }
    res_a = client.post("/api/v1/contacts", json=contact_a, headers=user_a_headers)
    c_a_id = res_a.json()["id"]

    # User B tries to GET User A's contact -> 403 Forbidden
    res_b_get = client.get(f"/api/v1/contacts/{c_a_id}", headers=user_b_headers)
    assert res_b_get.status_code == 403
    assert res_b_get.json()["error"]["code"] == "FORBIDDEN"

    # User B tries to UPDATE User A's contact -> 403 Forbidden
    res_b_put = client.put(
        f"/api/v1/contacts/{c_a_id}",
        json={"name": "Hacked Name"},
        headers=user_b_headers
    )
    assert res_b_put.status_code == 403

    # User B tries to DELETE User A's contact -> 403 Forbidden
    res_b_del = client.delete(f"/api/v1/contacts/{c_a_id}", headers=user_b_headers)
    assert res_b_del.status_code == 403

    # User B lists contacts -> should NOT see User A's contact
    res_b_list = client.get("/api/v1/contacts", headers=user_b_headers)
    assert res_b_list.status_code == 200
    assert len(res_b_list.json()) == 0


def test_create_contact_whitespace_name_rejected(client, user_a_headers):
    bad_contact = {
        "name": "   ",
        "phone": "+919811122233"
    }
    response = client.post("/api/v1/contacts", json=bad_contact, headers=user_a_headers)
    assert response.status_code == 422
