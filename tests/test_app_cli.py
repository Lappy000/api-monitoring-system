"""Offline tests for the installed application's console entry point."""

import importlib
from unittest.mock import patch

import pytest

from app.config import Config


@pytest.mark.parametrize("reload, expected_workers", [(False, 3), (True, 1)])
def test_console_entry_point_serves_fastapi_using_config(reload, expected_workers):
    cli = importlib.import_module("app.cli")
    config = Config()
    config.api.host = "127.0.0.1"
    config.api.port = 8765
    config.api.workers = 3
    config.api.reload = reload
    config.logging.level = "WARNING"

    with patch("app.cli.load_config", return_value=config), patch("uvicorn.run") as run:
        cli.main([])

    run.assert_called_once_with(
        "app.main:app",
        host="127.0.0.1",
        port=8765,
        reload=reload,
        workers=expected_workers,
        log_level="warning",
    )


@pytest.mark.parametrize("args, code", [(["--help"], 0), (["--unknown"], 2)])
def test_console_argument_handling_does_not_load_config_or_start_server(args, code, capsys):
    cli = importlib.import_module("app.cli")
    with patch("app.cli.load_config") as load, patch("uvicorn.run") as run:
        with pytest.raises(SystemExit) as exc:
            cli.main(args)
    assert exc.value.code == code
    load.assert_not_called()
    run.assert_not_called()
    output = capsys.readouterr()
    assert "usage:" in output.out + output.err
