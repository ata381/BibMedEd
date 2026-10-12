import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from bibmeded.config import Settings, unrecognised_env_vars


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


@pytest.fixture
def _no_pubmed_env(monkeypatch):
    monkeypatch.delenv("BIBMEDED_PUBMED_API_KEY", raising=False)
    monkeypatch.delenv("BIBMEDED_PUBMED_RATE_LIMIT", raising=False)


@pytest.mark.usefixtures("_no_pubmed_env")
def test_pubmed_rate_defaults_to_three_per_second_without_api_key():
    configured = Settings(_env_file=None)

    assert configured.pubmed_rate_limit is None
    assert configured.effective_pubmed_rate_limit() == 3.0


@pytest.mark.usefixtures("_no_pubmed_env")
def test_pubmed_rate_defaults_to_ten_per_second_with_api_key(monkeypatch):
    monkeypatch.setenv("BIBMEDED_PUBMED_API_KEY", "ncbi-key")

    assert Settings(_env_file=None).effective_pubmed_rate_limit() == 10.0


@pytest.mark.usefixtures("_no_pubmed_env")
def test_whitespace_only_api_key_keeps_keyless_rate(monkeypatch):
    monkeypatch.setenv("BIBMEDED_PUBMED_API_KEY", "   ")

    assert Settings(_env_file=None).effective_pubmed_rate_limit() == 3.0


@pytest.mark.usefixtures("_no_pubmed_env")
@pytest.mark.parametrize(
    ("api_key", "explicit", "expected"),
    [
        ("ncbi-key", "5", 5.0),
        ("", "8", 8.0),
        ("ncbi-key", "20", 20.0),
        ("", "0.5", 0.5),
    ],
)
def test_explicit_pubmed_rate_always_wins_and_is_never_clamped(monkeypatch, api_key, explicit, expected):
    monkeypatch.setenv("BIBMEDED_PUBMED_API_KEY", api_key)
    monkeypatch.setenv("BIBMEDED_PUBMED_RATE_LIMIT", explicit)

    assert Settings(_env_file=None).effective_pubmed_rate_limit() == expected


@pytest.mark.usefixtures("_no_pubmed_env")
@pytest.mark.parametrize("blank", ["", "  "])
def test_blank_pubmed_rate_counts_as_unset(monkeypatch, blank):
    # docker-compose forwards an unset ${BIBMEDED_PUBMED_RATE_LIMIT:-} as an empty string.
    monkeypatch.setenv("BIBMEDED_PUBMED_API_KEY", "ncbi-key")
    monkeypatch.setenv("BIBMEDED_PUBMED_RATE_LIMIT", blank)

    configured = Settings(_env_file=None)

    assert configured.pubmed_rate_limit is None
    assert configured.effective_pubmed_rate_limit() == 10.0


@pytest.mark.usefixtures("_no_pubmed_env")
@pytest.mark.parametrize("invalid", ["fast", "0", "-1", "nan", "inf"])
def test_invalid_pubmed_rate_fails_at_startup(monkeypatch, invalid):
    monkeypatch.setenv("BIBMEDED_PUBMED_RATE_LIMIT", invalid)

    with pytest.raises(ValidationError, match="pubmed_rate_limit"):
        Settings(_env_file=None)


def test_allow_lossy_downgrade_is_not_reported_as_unrecognised():
    environ = {"BIBMEDED_ALLOW_LOSSY_DOWNGRADE": "1", "BIBMEDED_ALLOW_LOSSY_DOWNGRAD": "1"}

    assert unrecognised_env_vars(environ) == ["BIBMEDED_ALLOW_LOSSY_DOWNGRAD"]
