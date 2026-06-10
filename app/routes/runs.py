from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ResumeRun, User
from app.db.session import get_db
from app.services.auth import current_user
from app.services.resume import resume_to_markdown

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _get_owned(db: Session, user: User, run_id: int) -> ResumeRun:
    run = db.get(ResumeRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    return run


@router.get("")
def list_runs(db: Session = Depends(get_db), user: User = Depends(current_user)) -> list[dict]:
    rows = db.scalars(
        select(ResumeRun).where(ResumeRun.user_id == user.id)
        .order_by(ResumeRun.created_at.desc())
    ).all()
    return [{"id": r.id, "target_role": r.target_role, "target_city": r.target_city,
             "model_used": r.model_used,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db),
            user: User = Depends(current_user)) -> dict:
    r = _get_owned(db, user, run_id)
    return {"id": r.id, "target_role": r.target_role, "target_industry": r.target_industry,
            "target_city": r.target_city, "work_type": r.work_type,
            "salary_expect": r.salary_expect, "notes": r.notes,
            "tailored_resume": r.tailored_resume, "recommendations": r.recommendations,
            "gaps": r.gaps, "model_used": r.model_used,
            "created_at": r.created_at.isoformat()}


@router.get("/{run_id}/markdown", response_class=PlainTextResponse)
def get_run_markdown(run_id: int, db: Session = Depends(get_db),
                     user: User = Depends(current_user)) -> str:
    r = _get_owned(db, user, run_id)
    return resume_to_markdown(r.tailored_resume)
