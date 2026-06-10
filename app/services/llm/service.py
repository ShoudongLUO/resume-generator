from __future__ import annotations

import json

from app.prompts.generate import GENERATE_PROMPT
from app.services.llm.base import LLMParseError, LLMUnavailable, parse_llm_json


def _build_prompt(profile: dict, intent: dict) -> str:
    return GENERATE_PROMPT.format(
        profile_json=json.dumps(profile, ensure_ascii=False, indent=2),
        target_role=intent.get("target_role") or "",
        target_industry=intent.get("target_industry") or "(未填)",
        target_city=intent.get("target_city") or "(未填)",
        work_type=intent.get("work_type") or "(未填)",
        salary_expect=intent.get("salary_expect") or "(未填)",
        notes=intent.get("notes") or "(无)",
    )


def _normalize(data: dict) -> dict:
    return {
        "tailored_resume": data.get("tailored_resume") or {},
        "recommendations": list(data.get("recommendations") or []),
        "gaps": list(data.get("gaps") or []),
    }


def generate_application(provider, profile: dict, intent: dict) -> dict:
    """Single LLM call returning {tailored_resume, recommendations, gaps}.

    Retries once with higher temperature on parse failure. LLMUnavailable
    (timeout/network) propagates to the caller.
    """
    prompt = _build_prompt(profile, intent)
    raw = provider.generate(prompt, temperature=0.6)
    try:
        return _normalize(parse_llm_json(raw))
    except LLMParseError:
        raw2 = provider.generate(prompt, temperature=0.8)
        return _normalize(parse_llm_json(raw2))
