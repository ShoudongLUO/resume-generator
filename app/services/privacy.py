from __future__ import annotations

import copy

# Privacy redaction for the LLM call. The profile is structured, so we know
# exactly which fields are contact info / company names and can tokenize them
# deterministically (no NLP). Contact info is dropped from basic_info entirely
# and any occurrence in free text is replaced with a token; company names become
# [公司N]. School / project / title / skills / city are retained.

_BASIC_KEEP = ("city", "status")


def _apply(obj, pairs):
    """Recursively replace every (from -> to) pair in all strings of obj."""
    if isinstance(obj, str):
        s = obj
        for frm, to in pairs:
            if frm:
                s = s.replace(frm, to)
        return s
    if isinstance(obj, list):
        return [_apply(x, pairs) for x in obj]
    if isinstance(obj, dict):
        return {k: _apply(v, pairs) for k, v in obj.items()}
    return obj


def redact_profile(profile: dict, enabled: bool):
    """Return (redacted_profile, restore_map).

    restore_map maps token -> real value, used later by restore_pii.
    When enabled is False the profile is returned unchanged with an empty map.
    """
    red = copy.deepcopy(profile or {})
    if not enabled:
        return red, {}

    b = profile.get("basic_info") or {}
    pairs = []  # (real, token), real -> token
    if b.get("name"):
        pairs.append((b["name"], "[姓名]"))
    if b.get("email"):
        pairs.append((b["email"], "[邮箱]"))
    if b.get("phone"):
        pairs.append((b["phone"], "[电话]"))
    for i, link in enumerate(b.get("links") or [], 1):
        if link:
            pairs.append((link, f"[链接{i}]"))

    seen = {}
    for exp in profile.get("experiences") or []:
        c = (exp.get("company") or "").strip()
        if c and c not in seen:
            seen[c] = f"[公司{len(seen) + 1}]"
            pairs.append((c, seen[c]))

    restore_map = {token: real for real, token in pairs}

    # Replace longer strings first so a shorter value can't partially clobber a
    # longer one that contains it.
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    red = _apply(red, pairs)

    # Drop contact fields from basic_info, keep only non-identifying ones.
    rb = red.get("basic_info") or {}
    red["basic_info"] = {k: rb[k] for k in _BASIC_KEEP if rb.get(k)}
    return red, restore_map


def restore_pii(result: dict, restore_map: dict, real_basic_info: dict) -> dict:
    """Replace tokens with real values across the LLM result, and overwrite the
    tailored resume's basic_info with the real (stored) contact info."""
    # Longer tokens first (e.g. [公司10] before [公司1]).
    pairs = sorted(restore_map.items(), key=lambda p: len(p[0]), reverse=True)
    out = _apply(copy.deepcopy(result or {}), pairs)
    if isinstance(out.get("tailored_resume"), dict):
        out["tailored_resume"]["basic_info"] = copy.deepcopy(real_basic_info or {})
    return out
