from app.config import Settings


def test_settings_reads_lens_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("BIBMEDED_LENS_API_KEY", "lens-environment-token")

    configured = Settings(_env_file=None)

    assert configured.lens_api_key == "lens-environment-token"
