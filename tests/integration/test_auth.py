def test_register_returns_token(client):
    r = client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["token"]
    assert r.json()["username"] == "bob"


def test_duplicate_username_409(client):
    client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    r = client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    assert r.status_code == 409


def test_login_success_and_failure(client):
    client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    ok = client.post("/api/auth/login", json={"username": "bob", "password": "password123"})
    assert ok.status_code == 200
    bad = client.post("/api/auth/login", json={"username": "bob", "password": "wrongpass1"})
    assert bad.status_code == 401


def test_protected_route_requires_auth(client):
    r = client.get("/api/profile")
    assert r.status_code == 401
