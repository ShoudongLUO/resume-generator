import app.routes.generate as gen
from app.services.llm.base import LLMParseError, LLMUnavailable


class _AvailProvider:
    available = True
    model = "fake-model"


def _fill_profile(client, h):
    client.put("/api/profile", json={
        "basic_info": {"name": "张三"}, "educations": [],
        "experiences": [{"company": "A", "title": "Dev", "bullets": ["x"]}],
        "projects": [], "skills": ["Python"], "self_summary": "",
    }, headers=h)


_RESULT = {
    "tailored_resume": {"basic_info": {"name": "张三"}, "summary": "s",
                        "educations": [], "experiences": [], "projects": [], "skills": []},
    "recommendations": [{"company": "A", "type": "互联网", "reason": "r", "suggested_role": "后端"}],
    "gaps": [{"gap": "g", "importance": "高", "suggestion": "s"}],
}


def test_generate_happy_path(client, auth_headers, monkeypatch):
    h = auth_headers()
    _fill_profile(client, h)
    monkeypatch.setattr(gen, "build_provider_for_user", lambda db, u: _AvailProvider())
    monkeypatch.setattr(gen, "generate_application", lambda p, prof, intent: _RESULT)
    r = client.post("/api/generate", json={"target_role": "后端工程师"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] > 0
    assert body["recommendations"][0]["company"] == "A"
    assert body["warning"] is None


def test_generate_profile_empty(client, auth_headers, monkeypatch):
    h = auth_headers()  # no profile filled
    monkeypatch.setattr(gen, "build_provider_for_user", lambda db, u: _AvailProvider())
    r = client.post("/api/generate", json={"target_role": "后端"}, headers=h)
    assert r.json()["error"] == "PROFILE_EMPTY"


def test_generate_llm_not_configured(client, auth_headers, monkeypatch):
    h = auth_headers()
    _fill_profile(client, h)

    class _Unavail:
        available = False
    monkeypatch.setattr(gen, "build_provider_for_user", lambda db, u: _Unavail())
    r = client.post("/api/generate", json={"target_role": "后端"}, headers=h)
    assert r.json()["error"] == "LLM_NOT_CONFIGURED"


def test_generate_parse_failed(client, auth_headers, monkeypatch):
    h = auth_headers()
    _fill_profile(client, h)
    monkeypatch.setattr(gen, "build_provider_for_user", lambda db, u: _AvailProvider())

    def _boom(p, prof, intent):
        raise LLMParseError("bad json")
    monkeypatch.setattr(gen, "generate_application", _boom)
    r = client.post("/api/generate", json={"target_role": "后端"}, headers=h)
    assert r.json()["error"] == "PARSE_FAILED"


def test_generate_llm_unavailable(client, auth_headers, monkeypatch):
    h = auth_headers()
    _fill_profile(client, h)
    monkeypatch.setattr(gen, "build_provider_for_user", lambda db, u: _AvailProvider())

    def _boom(p, prof, intent):
        raise LLMUnavailable("timeout")
    monkeypatch.setattr(gen, "generate_application", _boom)
    r = client.post("/api/generate", json={"target_role": "后端"}, headers=h)
    assert r.json()["error"] == "LLM_UNAVAILABLE"


def test_generate_quota_exceeded(client, auth_headers, monkeypatch):
    h = auth_headers()
    _fill_profile(client, h)
    monkeypatch.setattr(gen, "build_provider_for_user", lambda db, u: _AvailProvider())
    monkeypatch.setattr(gen, "generate_application", lambda p, prof, intent: _RESULT)
    monkeypatch.setattr(gen, "today_quota", lambda db, uid: 999)
    r = client.post("/api/generate", json={"target_role": "后端"}, headers=h)
    assert r.json()["error"] == "QUOTA_EXCEEDED"


def test_generate_then_appears_in_runs(client, auth_headers, monkeypatch):
    h = auth_headers()
    _fill_profile(client, h)
    monkeypatch.setattr(gen, "build_provider_for_user", lambda db, u: _AvailProvider())
    monkeypatch.setattr(gen, "generate_application", lambda p, prof, intent: _RESULT)
    run_id = client.post("/api/generate", json={"target_role": "后端"}, headers=h).json()["run_id"]
    runs = client.get("/api/runs", headers=h).json()
    assert any(x["id"] == run_id for x in runs)
    md = client.get(f"/api/runs/{run_id}/markdown", headers=h)
    assert md.status_code == 200 and "# 张三" in md.text
