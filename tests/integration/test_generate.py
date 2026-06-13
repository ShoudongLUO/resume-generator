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


class _CapturingProvider:
    available = True
    model = "fake-model"

    def __init__(self):
        self.prompt = None

    def generate(self, prompt, *, temperature=0.7):
        self.prompt = prompt
        return ('{"tailored_resume":{"basic_info":{},"summary":"在[公司1]工作",'
                '"experiences":[],"projects":[],"educations":[],"skills":[]},'
                '"recommendations":[{"company":"字节","type":"x","reason":"类似[公司1]","suggested_role":"后端"}],'
                '"gaps":[{"gap":"g","importance":"高","suggestion":"s"}]}')


def _fill_pii_profile(client, h):
    client.put("/api/profile", json={
        "basic_info": {"name": "张三", "email": "z@x.com", "phone": "13800000000", "city": "上海"},
        "educations": [{"school": "复旦大学", "major": "CS"}],
        "experiences": [{"company": "腾讯", "title": "后端", "description": "在腾讯做支付", "bullets": []}],
        "projects": [], "skills": ["Python"], "self_summary": "",
    }, headers=h)


def test_generate_privacy_on_redacts_prompt_and_restores(client, auth_headers, monkeypatch):
    h = auth_headers()
    _fill_pii_profile(client, h)
    prov = _CapturingProvider()
    monkeypatch.setattr(gen, "build_provider_for_user", lambda db, u: prov)
    r = client.post("/api/generate", json={"target_role": "后端", "privacy_mode": True}, headers=h).json()
    # prompt sent to the LLM must not contain real PII, but must contain the token
    assert "腾讯" not in prov.prompt
    assert "张三" not in prov.prompt
    assert "z@x.com" not in prov.prompt
    assert "[公司1]" in prov.prompt
    assert "复旦大学" in prov.prompt  # school retained
    # result returned to the user is restored to real values
    assert "腾讯" in r["tailored_resume"]["summary"]
    assert "腾讯" in r["recommendations"][0]["reason"]
    assert r["tailored_resume"]["basic_info"]["name"] == "张三"


def test_generate_privacy_off_sends_real(client, auth_headers, monkeypatch):
    h = auth_headers()
    _fill_pii_profile(client, h)
    prov = _CapturingProvider()
    monkeypatch.setattr(gen, "build_provider_for_user", lambda db, u: prov)
    client.post("/api/generate", json={"target_role": "后端", "privacy_mode": False}, headers=h)
    assert "腾讯" in prov.prompt
    assert "张三" in prov.prompt
