import uuid

import pytest
from fastapi import HTTPException

import app.services.llm.factory as factory
from app.db.models import LLMConfig
from app.services.auth import (
    AuthError, create_token, current_user, decode_token, hash_password, verify_password,
)
from app.services.crypto import encrypt
from app.services.llm.openai_compat import OpenAICompatProvider


class _FakeDB:
    def __init__(self, cfg):
        self._cfg = cfg

    def get(self, model, key):
        return self._cfg


class _User:
    id = uuid.uuid4()


def test_factory_none_config_unavailable():
    # No config and (in this project) no system GEMINI_API_KEY -> unavailable
    prov = factory._build_provider(None)
    assert prov.available is False


def test_factory_gemini_with_key(monkeypatch):
    captured = {}

    class _DummyGemini:
        def __init__(self, key, model):
            captured["key"] = key
            captured["model"] = model
            self.available = True
            self.model = model

    monkeypatch.setattr(factory, "GeminiProvider", _DummyGemini)
    cfg = LLMConfig(user_id=uuid.uuid4(), provider="gemini",
                    api_key_encrypted=encrypt("real-key"), model="gemini-2.5-pro")
    prov = factory._build_provider(cfg)
    assert captured["key"] == "real-key"
    assert captured["model"] == "gemini-2.5-pro"
    assert prov.available is True


def test_factory_openai_compat_with_key():
    cfg = LLMConfig(user_id=uuid.uuid4(), provider="openai_compat",
                    api_key_encrypted=encrypt("real-key"),
                    base_url="https://api.x.com/v1", model="gpt-x")
    prov = factory._build_provider(cfg)
    assert isinstance(prov, OpenAICompatProvider)
    assert prov.available is True


def test_factory_undecryptable_key_unavailable():
    cfg = LLMConfig(user_id=uuid.uuid4(), provider="gemini",
                    api_key_encrypted="not-valid-fernet", model="m")
    prov = factory._build_provider(cfg)
    assert prov.available is False


def test_factory_build_for_user(monkeypatch):
    monkeypatch.setattr(factory, "GeminiProvider",
                        lambda key, model: type("P", (), {"available": True, "model": model})())
    cfg = LLMConfig(user_id=uuid.uuid4(), provider="gemini",
                    api_key_encrypted=encrypt("k"), model="m")
    prov = factory.build_provider_for_user(_FakeDB(cfg), _User())
    assert prov.available is True


def test_password_hash_and_verify():
    h = hash_password("password123")
    assert verify_password("password123", h) is True
    assert verify_password("wrong", h) is False


def test_verify_bad_hash_returns_false():
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_token_roundtrip():
    uid = uuid.uuid4()
    t = create_token(user_id=uid, username="alice")
    payload = decode_token(t)
    assert payload["username"] == "alice"
    assert payload["sub"] == str(uid)


def test_decode_invalid_token_raises():
    with pytest.raises(AuthError):
        decode_token("garbage.token.value")


def test_current_user_missing_header():
    with pytest.raises(HTTPException) as e:
        current_user(authorization=None, db=None)
    assert e.value.status_code == 401


def test_current_user_bad_token():
    with pytest.raises(HTTPException) as e:
        current_user(authorization="Bearer garbage", db=None)
    assert e.value.status_code == 401
