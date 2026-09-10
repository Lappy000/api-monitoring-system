"""Argument contracts for the real app.cli launcher, never a live server."""

from unittest.mock import Mock

import pytest

from app import cli
from app.config import Config


@pytest.mark.parametrize("args", [["--help"], ["-h"]])
def test_help_is_successful_without_loading_config(args, monkeypatch, capsys):
    load = Mock(side_effect=AssertionError("help must not load config"))
    run = Mock(side_effect=AssertionError("help must not launch a server"))
    monkeypatch.setattr(cli, "load_config", load)
    monkeypatch.setattr(cli.uvicorn, "run", run)
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 0
    assert "FastAPI server" in capsys.readouterr().out
    load.assert_not_called()
    run.assert_not_called()


@pytest.mark.parametrize("args", [["valid_input"], [""], ["invalid!"], ["--port", "80"]])
def test_unsupported_arguments_fail_before_side_effects(args, monkeypatch, capsys):
    load = Mock(side_effect=AssertionError("invalid args must not load config"))
    run = Mock(side_effect=AssertionError("invalid args must not launch a server"))
    monkeypatch.setattr(cli, "load_config", load)
    monkeypatch.setattr(cli.uvicorn, "run", run)
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err
    load.assert_not_called()
    run.assert_not_called()


def test_none_argv_uses_process_arguments(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["api-monitoring-system", "--help"])
    load = Mock()
    run = Mock()
    monkeypatch.setattr(cli, "load_config", load)
    monkeypatch.setattr(cli.uvicorn, "run", run)
    with pytest.raises(SystemExit) as exc:
        cli.main(None)
    assert exc.value.code == 0
    assert "usage:" in capsys.readouterr().out
    load.assert_not_called()
    run.assert_not_called()


def test_empty_argv_uses_real_configuration_defaults(monkeypatch):
    config = Config()
    load = Mock(return_value=config)
    run = Mock()
    monkeypatch.setattr(cli, "load_config", load)
    monkeypatch.setattr(cli.uvicorn, "run", run)
    cli.main([])
    load.assert_called_once_with()
    run.assert_called_once_with(
        "app.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload,
        workers=1,
        log_level=config.logging.level.lower(),
    )


def test_configuration_failure_never_launches_server(monkeypatch):
    monkeypatch.setattr(cli, "load_config", Mock(side_effect=ValueError("bad config")))
    run = Mock()
    monkeypatch.setattr(cli.uvicorn, "run", run)
    with pytest.raises(ValueError, match="bad config"):
        cli.main([])
    run.assert_not_called()
