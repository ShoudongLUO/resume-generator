import pytest

from app.services.llm.base import LLMUnavailable
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.openai_compat import OpenAICompatProvider


# ---- GeminiProvider via injected transport ----

class _FakeTransport:
    def __init__(self, raise_on=None):
        self._raise_on = raise_on

    def generate(self, prompt, *, temperature=0.7):
        if self._raise_on == "generate":
            raise RuntimeError("boom")
        return "generated-text"

    def list_models(self):
        if self._raise_on == "list":
            raise RuntimeError("boom")
        return ["gemini-2.5-flash", "gemini-2.5-pro"]


def test_gemini_generate_with_transport():
    p = GeminiProvider("key", "gemini-2.5-flash", transport=_FakeTransport())
    assert p.available is True
    assert p.model == "gemini-2.5-flash"
    assert p.generate("hi") == "generated-text"


def test_gemini_list_models_with_transport():
    p = GeminiProvider("key", "m", transport=_FakeTransport())
    assert p.list_models() == ["gemini-2.5-flash", "gemini-2.5-pro"]


def test_gemini_generate_error_wrapped():
    p = GeminiProvider("key", "m", transport=_FakeTransport(raise_on="generate"))
    with pytest.raises(LLMUnavailable):
        p.generate("hi")


def test_gemini_list_models_error_wrapped():
    p = GeminiProvider("key", "m", transport=_FakeTransport(raise_on="list"))
    with pytest.raises(LLMUnavailable):
        p.list_models()


def test_gemini_no_key_unavailable():
    p = GeminiProvider("", "m")
    assert p.available is False
    with pytest.raises(LLMUnavailable):
        p.generate("hi")
    with pytest.raises(LLMUnavailable):
        p.list_models()


# ---- OpenAICompatProvider via injected http ----

class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _FakeHttp:
    def __init__(self, post_data=None, get_data=None, raise_exc=None):
        self._post_data = post_data
        self._get_data = get_data
        self._raise = raise_exc

    def post(self, *a, **k):
        if self._raise:
            raise self._raise
        return _Resp(self._post_data)

    def get(self, *a, **k):
        if self._raise:
            raise self._raise
        return _Resp(self._get_data)


def test_openai_generate_success():
    http = _FakeHttp(post_data={"choices": [{"message": {"content": "hello"}}]})
    p = OpenAICompatProvider("key", "https://api.x.com/v1", "gpt-x", http=http)
    assert p.available is True
    assert p.generate("hi") == "hello"


def test_openai_list_models_success():
    http = _FakeHttp(get_data={"data": [{"id": "m1"}, {"id": "m2"}]})
    p = OpenAICompatProvider("key", "https://api.x.com/v1", "gpt-x", http=http)
    assert p.list_models() == ["m1", "m2"]


def test_openai_generate_error_wrapped():
    http = _FakeHttp(raise_exc=RuntimeError("network down"))
    p = OpenAICompatProvider("key", "https://api.x.com/v1", "gpt-x", http=http)
    with pytest.raises(LLMUnavailable):
        p.generate("hi")


def test_openai_list_models_error_wrapped():
    http = _FakeHttp(raise_exc=RuntimeError("network down"))
    p = OpenAICompatProvider("key", "https://api.x.com/v1", "gpt-x", http=http)
    with pytest.raises(LLMUnavailable):
        p.list_models()


def test_openai_base_url_trailing_slash_stripped():
    http = _FakeHttp(get_data={"data": []})
    p = OpenAICompatProvider("key", "https://api.x.com/v1/", "gpt-x", http=http)
    assert p.list_models() == []
