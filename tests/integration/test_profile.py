def test_empty_profile_default(client, auth_headers):
    h = auth_headers()
    r = client.get("/api/profile", headers=h)
    assert r.status_code == 200
    assert r.json()["basic_info"] == {}
    assert r.json()["skills"] == []


def test_put_then_get_roundtrip(client, auth_headers):
    h = auth_headers()
    payload = {"basic_info": {"name": "张三"}, "educations": [],
               "experiences": [{"company": "A", "title": "Dev"}],
               "projects": [], "skills": ["Python"], "self_summary": "hi"}
    put = client.put("/api/profile", json=payload, headers=h)
    assert put.status_code == 200
    got = client.get("/api/profile", headers=h).json()
    assert got["basic_info"]["name"] == "张三"
    assert got["skills"] == ["Python"]


def test_profile_isolation_between_users(client, auth_headers):
    ha = auth_headers("alice", "password123")
    client.put("/api/profile", json={"basic_info": {"name": "Alice"}, "educations": [],
               "experiences": [], "projects": [], "skills": [], "self_summary": ""}, headers=ha)
    hb = auth_headers("bobby", "password123")
    got = client.get("/api/profile", headers=hb).json()
    assert got["basic_info"] == {}
