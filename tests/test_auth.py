def test_register_user_success(client):
    payload = {
        "name": "Pooja Verma",
        "email": "pooja@sakhi.safe",
        "phone": "+919123456780",
        "password": "Password789!"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Pooja Verma"
    assert data["email"] == "pooja@sakhi.safe"
    assert data["phone"] == "+919123456780"
    assert "password" not in data
    assert "password_hash" not in data
    assert "id" in data


def test_register_duplicate_email_fails(client, user_a):
    payload = {
        "name": "Another User",
        "email": user_a.email,  # same email as user_a
        "phone": "+919999999999",
        "password": "Password1234!"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CONFLICT"


def test_register_validation_errors(client):
    # Short password (< 8 chars)
    payload_short_pw = {
        "name": "Test User",
        "email": "test@sakhi.safe",
        "phone": "+919123456780",
        "password": "short"
    }
    res = client.post("/api/v1/auth/register", json=payload_short_pw)
    assert res.status_code == 422

    # Invalid email
    payload_bad_email = {
        "name": "Test User",
        "email": "not-an-email",
        "phone": "+919123456780",
        "password": "ValidPassword123!"
    }
    res = client.post("/api/v1/auth/register", json=payload_bad_email)
    assert res.status_code == 422


def test_login_success(client, user_a):
    payload = {
        "email": user_a.email,
        "password": "SecurePassword123!"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == user_a.email


def test_login_invalid_password(client, user_a):
    payload = {
        "email": user_a.email,
        "password": "WrongPassword999!"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_login_nonexistent_email(client):
    payload = {
        "email": "ghost@sakhi.safe",
        "password": "SomePassword123!"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401


def test_auth_me_authenticated(client, user_a, user_a_headers):
    response = client.get("/api/v1/auth/me", headers=user_a_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_a.id
    assert data["email"] == user_a.email


def test_auth_me_unauthorized(client):
    # No header
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

    # Bad token
    bad_headers = {"Authorization": "Bearer invalid.fake.token"}
    response = client.get("/api/v1/auth/me", headers=bad_headers)
    assert response.status_code == 401


def test_user_profile_update(client, user_a, user_a_headers):
    update_payload = {
        "name": "Aarya S. Verma",
        "phone": "+919988776655"
    }
    response = client.put("/api/v1/users/me", json=update_payload, headers=user_a_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Aarya S. Verma"
    assert data["phone"] == "+919988776655"


def test_logout(client, user_a_headers):
    response = client.post("/api/v1/auth/logout", headers=user_a_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"
