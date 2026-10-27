"""Command line and settings."""
import io
import json

import pytest

from tiroir import cli
from tiroir.auth import Password
from tiroir.config import from_env


def test_settings_defaults_and_values(tmp_path):
    cfg = from_env({"TIROIR_DATA_DIR": str(tmp_path), "TIROIR_PORT": "6000", "TIROIR_LANG": "fr-FR",
                    "TIROIR_AGENTS_DIR": str(tmp_path / "a"), "TIROIR_TRUST_PROXY": "yes"})
    assert (cfg.data_dir, cfg.port, cfg.lang, len(cfg.trust_proxy)) == (tmp_path, 6000, "fr", 2)
    assert cfg.agents_dir == tmp_path / "a"
    default = from_env({})
    assert default.host == "127.0.0.1" and default.agents_dir is None and default.cookie_secure == "auto" and default.lang == "en"


BAD = [{"TIROIR_PORT": "abc"}, {"TIROIR_PORT": "70000"}, {"TIROIR_COOKIE_SECURE": "maybe"}, {"TIROIR_TRUST_PROXY": "not-an-ip"}]


@pytest.mark.parametrize("env", BAD)
def test_bad_settings_fail_fast(env):
    with pytest.raises(SystemExit):
        from_env(env)


def test_set_password_from_stdin(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("a long enough password\n"))
    assert cli.main(["--data", str(tmp_path), "set-password", "--stdin"]) == 0
    assert Password(tmp_path).check("a long enough password")
    monkeypatch.setattr("sys.stdin", io.StringIO("short\n"))
    assert cli.main(["--data", str(tmp_path), "set-password", "--stdin"]) == 1
    assert "refused" in capsys.readouterr().err


def test_set_password_prompt_must_match(tmp_path, monkeypatch):
    answers = iter(["first password value", "other password value"])
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(answers))
    assert cli.main(["--data", str(tmp_path), "set-password"]) == 1
    assert not Password(tmp_path).is_set()


def test_export_logout_version(server, tmp_path, capsys):
    admin = server.login()
    server.call("PUT", "/api/notes/n1", admin, {"title": "exported"})
    out = tmp_path / "board.json"
    assert cli.main(["--data", str(server.data), "export", "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["notes"]["n1"]["title"] == "exported"
    assert cli.main(["--data", str(server.data), "logout-all"]) == 0
    assert server.call("GET", "/api/notes", admin).code == 401
    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.strip().endswith("1.0.0")


def test_serve_refuses_without_password(tmp_path, monkeypatch):
    monkeypatch.delenv("TIROIR_PASSWORD", raising=False)
    assert cli.main(["--data", str(tmp_path / "empty"), "serve"]) == 1


def test_first_run_password_from_env(tmp_path, monkeypatch):
    from tiroir.auth import first_run_password
    pw = Password(tmp_path)
    first_run_password(pw, {"TIROIR_PASSWORD": "docker compose secret"})
    assert pw.check("docker compose secret")
    first_run_password(pw, {"TIROIR_PASSWORD": "another one, ignored"})
    assert pw.check("docker compose secret")
