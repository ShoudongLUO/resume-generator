import app.db.session as session


def _clear_db_env(monkeypatch):
    for name in session._DB_URL_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_explicit_url_wins(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://env/db")
    assert session._resolve_url("sqlite:///x.db") == "sqlite:///x.db"


def test_database_url_preferred(monkeypatch):
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://a/db")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://b/db")
    assert session._resolve_url() == "postgresql://a/db"


def test_falls_back_to_postgres_url(monkeypatch):
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_URL", "postgresql://b/db")
    assert session._resolve_url() == "postgresql://b/db"


def test_falls_back_to_non_pooling(monkeypatch):
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_URL_NON_POOLING", "postgresql://c/db")
    assert session._resolve_url() == "postgresql://c/db"


def test_defaults_to_sqlite_when_unset(monkeypatch):
    _clear_db_env(monkeypatch)
    assert session._resolve_url() == "sqlite:///./data.db"


def test_normalize_converts_postgres_scheme():
    assert session._normalize_url("postgres://u:p@h/db").startswith("postgresql+psycopg://")
    assert session._normalize_url("postgresql://u:p@h/db").startswith("postgresql+psycopg://")
    # already-normalized and sqlite pass through unchanged
    assert session._normalize_url("postgresql+psycopg://h/db") == "postgresql+psycopg://h/db"
    assert session._normalize_url("sqlite:///./data.db") == "sqlite:///./data.db"
