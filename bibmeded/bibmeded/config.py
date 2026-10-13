from collections.abc import Mapping

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

ENV_PREFIX = "BIBMEDED_"
# Read directly from os.environ outside Settings (bibmeded/main.py and
# alembic/versions/0004_screening_stage.py).
NON_SETTINGS_ENV_VARS = frozenset({"BIBMEDED_LOG_LEVEL", "BIBMEDED_ALLOW_LOSSY_DOWNGRADE"})

# NCBI E-utilities allowances: https://www.ncbi.nlm.nih.gov/books/NBK25497/
PUBMED_RATE_LIMIT_WITHOUT_KEY = 3.0
PUBMED_RATE_LIMIT_WITH_KEY = 10.0


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://bibmeded:bibmeded@localhost:5432/bibmeded"
    redis_url: str = "redis://localhost:6379/0"
    pubmed_api_key: str = ""
    # None means "derive from whether a key is set"; see effective_pubmed_rate_limit.
    pubmed_rate_limit: float | None = Field(default=None, gt=0, allow_inf_nan=False)
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

    @field_validator("pubmed_rate_limit", mode="before")
    @classmethod
    def _blank_rate_limit_is_unset(cls, value: object) -> object:
        # docker-compose passes an unset ${BIBMEDED_PUBMED_RATE_LIMIT:-} through as "".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def effective_pubmed_rate_limit(self) -> float:
        if self.pubmed_rate_limit is not None:
            return self.pubmed_rate_limit
        if self.pubmed_api_key.strip():
            return PUBMED_RATE_LIMIT_WITH_KEY
        return PUBMED_RATE_LIMIT_WITHOUT_KEY

    model_config = {"env_prefix": ENV_PREFIX}


def unrecognised_env_vars(environ: Mapping[str, str]) -> list[str]:
    known = {f"{ENV_PREFIX}{name}".upper() for name in Settings.model_fields} | NON_SETTINGS_ENV_VARS
    return sorted(
        name for name in environ
        if name.upper().startswith(ENV_PREFIX) and name.upper() not in known
    )


settings = Settings()
