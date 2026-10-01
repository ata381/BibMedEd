from typing import NamedTuple

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


class RequiredSetting(NamedTuple):
    attribute: str
    env_var: str
    # Separate from the adapter's display_name so messages can use the short brand
    # ("Lens", not "Lens.org") without importing the adapter registry here.
    label: str


REQUIRED_SETTINGS: dict[str, RequiredSetting] = {
    "lens": RequiredSetting("lens_api_key", "BIBMEDED_LENS_API_KEY", "Lens"),
}


def required_setting_env_var(source: str) -> str | None:
    requirement = REQUIRED_SETTINGS.get(source)
    return requirement.env_var if requirement else None


def adapter_configuration_error(source: str) -> str | None:
    requirement = REQUIRED_SETTINGS.get(source)
    if requirement is None:
        return None
    if str(getattr(settings, requirement.attribute) or "").strip():
        return None
    return f"{requirement.label} searches require {requirement.env_var}"
