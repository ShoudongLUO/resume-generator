from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import LLMConfig, User
from app.services.crypto import decrypt
from app.services.llm.base import LLMUnavailable
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.openai_compat import OpenAICompatProvider


class _UnavailableProvider:
    available = False
    model = ""

    def __init__(self, reason: str = "no LLM configured"):
        self._reason = reason

    def generate(self, prompt: str, *, temperature: float = 0.7) -> str:
        raise LLMUnavailable(self._reason)

    def list_models(self) -> list[str]:
        raise LLMUnavailable(self._reason)


def _build_provider(cfg: LLMConfig | None):
    if cfg and cfg.api_key_encrypted:
        try:
            key = decrypt(cfg.api_key_encrypted)
        except Exception:  # noqa: BLE001 - bad ciphertext (e.g. LLM_ENC_KEY rotated)
            return _UnavailableProvider("saved API key could not be decrypted")
        if cfg.provider == "openai_compat":
            return OpenAICompatProvider(key, cfg.base_url or "", cfg.model or "")
        return GeminiProvider(key, cfg.model or settings.gemini_model)
    if settings.gemini_api_key:
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    return _UnavailableProvider()


def build_provider_for_user(db: Session, user: User):
    return _build_provider(db.get(LLMConfig, user.id))
