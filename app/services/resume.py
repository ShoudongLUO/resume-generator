from __future__ import annotations


def _contact_line(b: dict) -> str:
    parts = [b.get("phone"), b.get("email"), b.get("city")]
    parts += list(b.get("links") or [])
    return " | ".join(str(p) for p in parts if p)


def resume_to_markdown(resume: dict) -> str:
    resume = resume or {}
    b = resume.get("basic_info") or {}
    lines: list[str] = []

    name = b.get("name")
    if name:
        lines.append(f"# {name}")
    contact = _contact_line(b)
    if contact:
        lines.append(contact)

    summary = (resume.get("summary") or "").strip()
    if summary:
        lines += ["", "## 个人概述", summary]

    educations = resume.get("educations") or []
    if educations:
        lines += ["", "## 教育经历"]
        for e in educations:
            head = " · ".join(str(x) for x in [e.get("school"), e.get("major"),
                                               e.get("degree")] if x)
            span = "–".join(str(x) for x in [e.get("start"), e.get("end")] if x)
            lines.append(f"- **{head}** {span}".rstrip())
            if e.get("highlights"):
                lines.append(f"  - {e['highlights']}")

    experiences = resume.get("experiences") or []
    if experiences:
        lines += ["", "## 工作经历"]
        for x in experiences:
            head = " · ".join(str(v) for v in [x.get("company"), x.get("title")] if v)
            span = "–".join(str(v) for v in [x.get("start"), x.get("end")] if v)
            lines.append(f"### {head} {span}".rstrip())
            for bullet in (x.get("bullets") or []):
                lines.append(f"- {bullet}")
            if x.get("description"):
                lines.append(str(x["description"]))

    projects = resume.get("projects") or []
    if projects:
        lines += ["", "## 项目经历"]
        for p in projects:
            head = " · ".join(str(v) for v in [p.get("name"), p.get("role")] if v)
            lines.append(f"### {head}".rstrip())
            if p.get("tech_stack"):
                lines.append(f"技术栈：{p['tech_stack']}")
            if p.get("description"):
                lines.append(str(p["description"]))
            if p.get("outcome"):
                lines.append(f"成果：{p['outcome']}")

    skills = resume.get("skills") or []
    if skills:
        lines += ["", "## 技能", " · ".join(str(s) for s in skills)]

    return "\n".join(lines).strip() + "\n"
