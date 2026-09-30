import pytest
from sqlalchemy.engine import make_url

from app.config import Settings


def test_settings_reads_lens_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("BIBMEDED_LENS_API_KEY", "lens-environment-token")

    configured = Settings(_env_file=None)

    assert configured.lens_api_key == "lens-environment-token"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@h:5432/d", "postgresql+psycopg2://u:p@h:5432/d"),
        ("postgresql://u:p@h:5432/d", "postgresql+psycopg2://u:p@h:5432/d"),
        ("postgresql+psycopg2://u:p@h:5432/d", "postgresql+psycopg2://u:p@h:5432/d"),
        ("postgresql+psycopg://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("sqlite:///./bibmeded.db", "sqlite:///./bibmeded.db"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_database_url_is_normalised_to_explicit_driver(monkeypatch, raw, expected):
    monkeypatch.setenv("BIBMEDED_DATABASE_URL", raw)

    assert Settings(_env_file=None).database_url == expected


def test_default_database_url_uses_psycopg2_driver(monkeypatch):
    monkeypatch.delenv("BIBMEDED_DATABASE_URL", raising=False)

    url = make_url(Settings(_env_file=None).database_url)

    assert url.get_dialect().driver == "psycopg2"
