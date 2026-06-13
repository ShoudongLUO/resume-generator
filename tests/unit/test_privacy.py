from app.services.privacy import redact_profile, restore_pii

PROFILE = {
    "basic_info": {"name": "张三", "email": "z@x.com", "phone": "13800000000",
                   "city": "上海", "links": ["github.com/zhang"]},
    "summary": "张三在腾讯负责后端",
    "experiences": [
        {"company": "腾讯", "title": "后端", "start": "2020", "end": "2023", "description": "在腾讯做支付"},
        {"company": "阿里巴巴", "title": "工程师", "description": "阿里巴巴项目"},
    ],
    "educations": [{"school": "复旦大学", "major": "CS"}],
    "projects": [{"name": "订单系统", "description": "腾讯订单"}],
    "skills": ["Python"],
    "self_summary": "联系 z@x.com",
}


def test_disabled_returns_unchanged():
    red, m = redact_profile(PROFILE, False)
    assert red == PROFILE
    assert m == {}


def test_contact_stripped_from_basic_info():
    red, _ = redact_profile(PROFILE, True)
    bi = red["basic_info"]
    assert "name" not in bi and "email" not in bi and "phone" not in bi and "links" not in bi
    assert bi.get("city") == "上海"


def test_company_tokenized_school_kept():
    red, _ = redact_profile(PROFILE, True)
    assert [e["company"] for e in red["experiences"]] == ["[公司1]", "[公司2]"]
    assert red["educations"][0]["school"] == "复旦大学"


def test_no_real_pii_in_redacted_blob():
    red, _ = redact_profile(PROFILE, True)
    blob = str(red)
    for leak in ["张三", "z@x.com", "13800000000", "腾讯", "阿里巴巴", "github.com/zhang"]:
        assert leak not in blob, f"leaked: {leak}"
    assert "复旦大学" in blob  # school retained


def test_freetext_contact_and_company_replaced():
    red, _ = redact_profile(PROFILE, True)
    assert "张三" not in red["summary"] and "[姓名]" in red["summary"]
    assert "腾讯" not in red["summary"] and "[公司1]" in red["summary"]
    assert "[邮箱]" in red["self_summary"]


def test_restore_roundtrip():
    _, m = redact_profile(PROFILE, True)
    llm_result = {
        "tailored_resume": {"basic_info": {}, "summary": "在[公司1]与[公司2]的经验",
                            "experiences": [], "projects": [], "educations": [], "skills": []},
        "recommendations": [{"company": "字节", "reason": "类似[公司1]的经验"}],
        "gaps": [{"gap": "x", "importance": "高", "suggestion": "y"}],
    }
    out = restore_pii(llm_result, m, PROFILE["basic_info"])
    assert "腾讯" in out["tailored_resume"]["summary"]
    assert "阿里巴巴" in out["tailored_resume"]["summary"]
    assert "腾讯" in out["recommendations"][0]["reason"]
    assert out["tailored_resume"]["basic_info"]["name"] == "张三"
    assert "[公司1]" not in str(out)
