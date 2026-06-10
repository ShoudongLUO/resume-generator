from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import ResumeProfile, User
from app.db.session import get_db
from app.services.auth import current_user

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileIn(BaseModel):
    basic_info: dict = Field(default_factory=dict)
    educations: list = Field(default_factory=list)
    experiences: list = Field(default_factory=list)
    projects: list = Field(default_factory=list)
    skills: list = Field(default_factory=list)
    self_summary: str = ""


class ProfileOut(ProfileIn):
    pass


def _empty() -> ProfileOut:
    return ProfileOut(basic_info={}, educations=[], experiences=[],
                      projects=[], skills=[], self_summary="")


@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = db.get(ResumeProfile, user.id)
    if p is None:
        return _empty()
    return ProfileOut(basic_info=p.basic_info, educations=p.educations,
                      experiences=p.experiences, projects=p.projects,
                      skills=p.skills, self_summary=p.self_summary)


@router.put("", response_model=ProfileOut)
def put_profile(body: ProfileIn, db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    p = db.get(ResumeProfile, user.id)
    if p is None:
        p = ResumeProfile(user_id=user.id)
        db.add(p)
    p.basic_info = body.basic_info
    p.educations = body.educations
    p.experiences = body.experiences
    p.projects = body.projects
    p.skills = body.skills
    p.self_summary = body.self_summary
    p.updated_at = datetime.utcnow()
    db.commit()
    return body
