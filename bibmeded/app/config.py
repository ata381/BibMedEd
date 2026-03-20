from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://bibmeded:bibmeded@localhost:5432/bibmeded"
    redis_url: str = "redis://localhost:6379/0"
    pubmed_api_key: str = ""
    pubmed_rate_limit: float = 3.0  # requests/sec, 10 with API key
    icite_base_url: str = "https://icite.od.nih.gov/api"
    debug: bool = False

    model_config = {"env_prefix": "BIBMEDED_"}


settings = Settings()
