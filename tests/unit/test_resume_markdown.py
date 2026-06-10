from app.services.resume import resume_to_markdown


def test_full_resume_renders_all_sections():
    resume = {
        "basic_info": {"name": "张三", "email": "z@x.com", "phone": "13800000000",
                       "city": "上海", "links": ["github.com/z"]},
        "summary": "三年后端经验",
        "educations": [{"school": "复旦", "major": "计算机", "degree": "本科",
                        "start": "2016", "end": "2020"}],
        "experiences": [{"company": "A公司", "title": "后端工程师", "start": "2020",
                         "end": "2023", "bullets": ["优化接口性能50%", "主导支付重构"]}],
        "projects": [{"name": "订单系统", "role": "负责人", "tech_stack": "Python/PG",
                      "description": "高并发订单", "outcome": "QPS 提升3倍"}],
        "skills": ["Python", "PostgreSQL"],
    }
    md = resume_to_markdown(resume)
    assert "# 张三" in md
    assert "## 个人概述" in md and "三年后端经验" in md
    assert "## 教育经历" in md and "复旦" in md
    assert "## 工作经历" in md and "优化接口性能50%" in md
    assert "## 项目经历" in md and "订单系统" in md
    assert "## 技能" in md and "Python" in md


def test_empty_sections_are_skipped():
    resume = {"basic_info": {"name": "李四"}, "summary": "",
              "educations": [], "experiences": [], "projects": [], "skills": []}
    md = resume_to_markdown(resume)
    assert "# 李四" in md
    assert "## 教育经历" not in md
    assert "## 工作经历" not in md
    assert "## 技能" not in md
    assert "## 个人概述" not in md


def test_missing_keys_do_not_crash():
    md = resume_to_markdown({})
    assert isinstance(md, str)
