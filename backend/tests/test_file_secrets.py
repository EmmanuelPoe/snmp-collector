"""File-backed secrets (Step 4.4): <NAME>_FILE hydrates <NAME> from a file
(docker/compose secrets) unless <NAME> is already set explicitly."""

import os

import config


def test_file_secret_hydrates_when_env_unset(tmp_path, monkeypatch):
    f = tmp_path / "jwt"
    f.write_text("  a-very-strong-secret-value\n")  # surrounding whitespace stripped
    monkeypatch.delenv("SAMPLE_SECRET", raising=False)
    monkeypatch.setenv("SAMPLE_SECRET_FILE", str(f))

    config._hydrate_file_secrets("SAMPLE_SECRET")

    assert os.environ["SAMPLE_SECRET"] == "a-very-strong-secret-value"


def test_explicit_env_takes_precedence_over_file(tmp_path, monkeypatch):
    f = tmp_path / "jwt"
    f.write_text("from-file")
    monkeypatch.setenv("SAMPLE_SECRET", "from-env")
    monkeypatch.setenv("SAMPLE_SECRET_FILE", str(f))

    config._hydrate_file_secrets("SAMPLE_SECRET")

    assert os.environ["SAMPLE_SECRET"] == "from-env"


def test_missing_file_is_ignored(monkeypatch):
    monkeypatch.delenv("SAMPLE_SECRET", raising=False)
    monkeypatch.setenv("SAMPLE_SECRET_FILE", "/no/such/file")

    config._hydrate_file_secrets("SAMPLE_SECRET")

    assert "SAMPLE_SECRET" not in os.environ
