from pathlib import Path

import pytest
import yaml

from bibmeded.config import Settings

COMPOSE_FILE = Path(__file__).resolve().parents[1] / "docker-compose.yml"

FORWARDED_FROM_DOTENV = (
    "BIBMEDED_PUBMED_API_KEY",
    "BIBMEDED_PUBMED_RATE_LIMIT",
    "BIBMEDED_NCBI_EMAIL",
    "BIBMEDED_OPENALEX_EMAIL",
    "BIBMEDED_CROSSREF_EMAIL",
    "BIBMEDED_SEMANTIC_SCHOLAR_API_KEY",
    "BIBMEDED_LENS_API_KEY",
)


@pytest.fixture(scope="module")
def services() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"]


@pytest.mark.parametrize("service", ["api", "worker"])
@pytest.mark.parametrize("env_var", FORWARDED_FROM_DOTENV)
def test_source_settings_reach_api_and_worker(services, service, env_var):
    assert services[service]["environment"][env_var] == f"${{{env_var}:-}}"


@pytest.mark.parametrize("env_var", FORWARDED_FROM_DOTENV)
def test_forwarded_names_are_real_settings(env_var):
    field = env_var.removeprefix("BIBMEDED_").lower()

    assert field in Settings.model_fields
