from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ResumeProfile, ResumeRun, User
from app.db.session import get_db
from app.services.auth import current_user
from app.services.llm.base import LLMParseError, LLMUnavailable
from app.services.llm.factory import build_provider_for_user
from app.services.llm.service import generate_application
from app.services.quota import bump_quota, today_quota

router = APIRouter(prefix="/api", tags=["generate"])


class GenerateIn(BaseModel):
    target_role: str
    target_industry: str | None = None
    target_city: str | None = None
    work_type: str | None = None
    salary_expect: str | None = None
    notes: str | None = None


def _profile_empty(p: ResumeProfile | None) -> bool:
    if p is None:
        return True
    has_name = bool((p.basic_info or {}).get("name"))
    has_history = bool(p.experiences) or bool(p.educations) or bool(p.projects)
    return not (has_name and has_history)


@router.post("/generate")
def generate(body: GenerateIn, db: Session = Depends(get_db),
             user: User = Depends(current_user)) -> dict:
    if not body.target_role.strip():
        return {"error": "TARGET_ROLE_REQUIRED"}

    profile = db.get(ResumeProfile, user.id)
    if _profile_empty(profile):
        return {"error": "PROFILE_EMPTY"}

    provider = build_provider_for_user(db, user)
    if not getattr(provider, "available", False):
        return {"error": "LLM_NOT_CONFIGURED"}

    if today_quota(db, user.id) >= settings.daily_generate_quota:
        return {"error": "QUOTA_EXCEEDED"}

    profile_dict = {
        "basic_info": profile.basic_info, "educations": profile.educations,
        "experiences": profile.experiences, "projects": profile.projects,
        "skills": profile.skills, "self_summary": profile.self_summary,
    }
    intent = body.model_dump()
    try:
        result = generate_application(provider, profile_dict, intent)
    except LLMUnavailable:
        return {"error": "LLM_UNAVAILABLE"}
    except LLMParseError:
        return {"error": "PARSE_FAILED"}

    bump_quota(db, user.id)
    run = ResumeRun(
        user_id=user.id, target_role=body.target_role,
        target_industry=body.target_industry, target_city=body.target_city,
        work_type=body.work_type, salary_expect=body.salary_expect, notes=body.notes,
        tailored_resume=result["tailored_resume"],
        recommendations=result["recommendations"], gaps=result["gaps"],
        model_used=getattr(provider, "model", None),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    warning = None
    if not result["recommendations"] or not result["gaps"]:
        warning = "部分内容生成不完整，可重试"
    return {
        "run_id": run.id,
        "tailored_resume": result["tailored_resume"],
        "recommendations": result["recommendations"],
        "gaps": result["gaps"],
        "model_used": run.model_used,
        "warning": warning,
    }
