from bibmeded.config import settings


_ADAPTER_KWARGS_BUILDERS = {
    "pubmed": lambda: {
        "api_key": settings.pubmed_api_key,
        "rate_limit": settings.pubmed_rate_limit,
    },
    "openalex": lambda: {"email": settings.openalex_email},
    "crossref": lambda: {"email": settings.crossref_email},
    "semanticscholar": lambda: {"api_key": settings.semantic_scholar_api_key},
    "lens": lambda: {"api_key": settings.lens_api_key},
}


def adapter_kwargs(source: str) -> dict:
    builder = _ADAPTER_KWARGS_BUILDERS.get(source)
    return builder() if builder else {}


_REQUIRED_SETTING_ENV_VARS = {"lens": "BIBMEDED_LENS_API_KEY"}


def required_setting_env_var(source: str) -> str | None:
    return _REQUIRED_SETTING_ENV_VARS.get(source)


def adapter_configuration_error(source: str) -> str | None:
    if source == "lens" and not settings.lens_api_key.strip():
        return f"Lens searches require {required_setting_env_var(source)}"
    return None
