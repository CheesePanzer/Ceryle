import os
import subprocess
import sys

import pytest

import settings


@pytest.mark.parametrize("value", [None, "", "   "])
def test_require_env_rejects_missing_or_blank_values(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("REQUIRED_TEST_VALUE", raising=False)
    else:
        monkeypatch.setenv("REQUIRED_TEST_VALUE", value)

    with pytest.raises(RuntimeError, match="REQUIRED_TEST_VALUE"):
        settings.require_env("REQUIRED_TEST_VALUE")


@pytest.mark.parametrize("missing_name", ["API_KEY", "SESSION_SECRET"])
def test_settings_import_fails_without_required_secret(missing_name):
    env = os.environ.copy()
    env["API_KEY"] = "test-api-key"
    env["SESSION_SECRET"] = "test-session-secret"
    env.pop(missing_name)

    result = subprocess.run(
        [sys.executable, "-c", "import settings"],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert f"Required environment variable {missing_name} is not set" in result.stderr
