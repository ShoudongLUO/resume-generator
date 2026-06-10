import json

import pytest

from app.services.llm.base import LLMParseError, LLMUnavailable
from app.services.llm.service import generate_application


class _FakeProvider:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.model = "fake-model"

    def generate(self, prompt, *, temperature=0.7):
        self.calls += 1
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


_GOOD = json.dumps({
    "tailored_resume": {"basic_info": {"name": "张三"}, "summary": "s",
                        "educations": [], "experiences": [], "projects": [], "skills": []},
    "recommendations": [{"company": "A", "type": "互联网", "reason": "r", "suggested_role": "后端"}],
    "gaps": [{"gap": "缺算法", "importance": "高", "suggestion": "刷题"}],
})

_INTENT = {"target_role": "后端", "target_industry": "", "target_city": "",
           "work_type": "", "salary_expect": "", "notes": ""}
_PROFILE = {"basic_info": {"name": "张三"}, "educations": [], "experiences": [],
            "projects": [], "skills": [], "self_summary": ""}


def test_generate_parses_three_parts():
    p = _FakeProvider([_GOOD])
    result = generate_application(p, _PROFILE, _INTENT)
    assert result["tailored_resume"]["basic_info"]["name"] == "张三"
    assert result["recommendations"][0]["company"] == "A"
    assert result["gaps"][0]["importance"] == "高"
    assert p.calls == 1


def test_generate_retries_once_on_parse_failure():
    p = _FakeProvider(["这不是 JSON", _GOOD])
    result = generate_application(p, _PROFILE, _INTENT)
    assert result["recommendations"][0]["company"] == "A"
    assert p.calls == 2


def test_generate_raises_after_second_parse_failure():
    p = _FakeProvider(["garbage", "still garbage"])
    with pytest.raises(LLMParseError):
        generate_application(p, _PROFILE, _INTENT)


def test_generate_propagates_unavailable():
    p = _FakeProvider([LLMUnavailable("timeout")])
    with pytest.raises(LLMUnavailable):
        generate_application(p, _PROFILE, _INTENT)


def test_missing_part_defaults_to_empty():
    partial = json.dumps({"tailored_resume": {"basic_info": {"name": "李四"}}})
    p = _FakeProvider([partial])
    result = generate_application(p, _PROFILE, _INTENT)
    assert result["recommendations"] == []
    assert result["gaps"] == []
