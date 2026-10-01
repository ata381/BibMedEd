from bibmeded.adapters import settings as adapter_settings
from bibmeded.adapters.settings import (
    RequiredSetting,
    adapter_configuration_error,
    required_setting_env_var,
)
from bibmeded.config import settings


def test_lens_without_key_reports_unchanged_message(monkeypatch):
    monkeypatch.setattr(settings, "lens_api_key", "  ")

    assert adapter_configuration_error("lens") == "Lens searches require BIBMEDED_LENS_API_KEY"


def test_lens_with_key_has_no_configuration_error(monkeypatch):
    monkeypatch.setattr(settings, "lens_api_key", "lens-token")

    assert adapter_configuration_error("lens") is None


def test_unkeyed_and_unknown_sources_have_no_requirement():
    assert adapter_configuration_error("pubmed") is None
    assert required_setting_env_var("pubmed") is None
    assert adapter_configuration_error("does-not-exist") is None


def test_new_keyed_source_gets_behaviour_from_table_entry(monkeypatch):
    # Settings is a pydantic model that rejects unknown attributes, so the fake
    # source borrows an existing setting the table has never referenced.
    monkeypatch.setattr(settings, "semantic_scholar_api_key", "")
    monkeypatch.setitem(
        adapter_settings.REQUIRED_SETTINGS,
        "fakesource",
        RequiredSetting(
            attribute="semantic_scholar_api_key",
            env_var="BIBMEDED_FAKESOURCE_API_KEY",
            label="FakeSource",
        ),
    )

    assert required_setting_env_var("fakesource") == "BIBMEDED_FAKESOURCE_API_KEY"
    assert (
        adapter_configuration_error("fakesource")
        == "FakeSource searches require BIBMEDED_FAKESOURCE_API_KEY"
    )

    monkeypatch.setattr(settings, "semantic_scholar_api_key", "configured")

    assert adapter_configuration_error("fakesource") is None


def test_every_required_setting_names_an_existing_settings_attribute():
    for source, requirement in adapter_settings.REQUIRED_SETTINGS.items():
        assert hasattr(settings, requirement.attribute), source


def test_fake_source_does_not_leak_into_table():
    assert "fakesource" not in adapter_settings.REQUIRED_SETTINGS
