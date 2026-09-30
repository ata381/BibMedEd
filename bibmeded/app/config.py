from collections.abc import Mapping

from pydantic import field_validator
from pydantic_settings import BaseSettings

ENV_PREFIX = "BIBMEDED_"
# Read directly from os.environ outside Settings (see app/main.py).
NON_SETTINGS_ENV_VARS = frozenset({"BIBMEDED_LOG_LEVEL"})


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://bibmeded:bibmeded@localhost:5432/bibmeded"
    redis_url: str = "redis://localhost:6379/0"
    pubmed_api_key: str = ""
    pubmed_rate_limit: float = 3.0  # requests/sec, 10 with API key
    ncbi_email: str = ""
    openalex_email: str = ""
    crossref_email: str = ""
    semantic_scholar_api_key: str = ""  # optional — keyed S2 tier is 1 req/s instead of ~100/5min
    lens_api_key: str = ""
    icite_base_url: str = "https://icite.od.nih.gov/api"
    cors_origins: list[str] = ["http://localhost:3000"]
    debug: bool = False
    read_only: bool = False

    @field_validator("database_url")
    @classmethod
    def _pin_postgres_driver(cls, value: str) -> str:
        # SQLAlchemy 2.1 changed the bare postgresql:// default driver from
        # psycopg2 to psycopg (v3), which we don't install. Render also injects
        # the legacy postgres:// scheme, which SQLAlchemy rejects outright.
        for bare in ("postgres://", "postgresql://"):
            if value.startswith(bare):
                return "postgresql+psycopg2://" + value[len(bare):]
        return value

    model_config = {"env_prefix": ENV_PREFIX}


def unrecognised_env_vars(environ: Mapping[str, str]) -> list[str]:
    known = {f"{ENV_PREFIX}{name}".upper() for name in Settings.model_fields} | NON_SETTINGS_ENV_VARS
    return sorted(
        name for name in environ
        if name.upper().startswith(ENV_PREFIX) and name.upper() not in known
    )


settings = Settings()
