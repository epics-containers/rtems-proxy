"""
Tests that conserver support (use_console) is threaded through the start
command to TelnetRTEMS, via both the CLI flag and RTEMS_USE_CONSOLE env var.
"""

import pytest
from typer.testing import CliRunner

import rtems_proxy.__main__ as main_mod
from rtems_proxy.globals import GLOBALS, reload_globals
from rtems_proxy.telnet import TelnetRTEMS


@pytest.fixture
def captured(monkeypatch):
    calls: dict = {}

    def fake_ioc_connect(host_and_port, **kwargs):
        calls["host_and_port"] = host_and_port
        calls.update(kwargs)

    monkeypatch.setattr(main_mod, "ioc_connect", fake_ioc_connect)
    monkeypatch.setattr(main_mod, "check_new_version", lambda: False)
    monkeypatch.setattr(main_mod, "save_current_version", lambda: None)
    monkeypatch.setenv("RTEMS_CONSOLE", "BL19I-VA-IOC-01")
    yield calls
    monkeypatch.delenv("RTEMS_CONSOLE", raising=False)
    monkeypatch.delenv("RTEMS_USE_CONSOLE", raising=False)
    reload_globals()


@pytest.mark.parametrize(
    "env, args, expected",
    [
        (None, [], False),
        (None, ["--use-console"], True),
        ("true", [], True),
        ("1", ["--no-use-console"], False),
        ("false", [], False),
    ],
)
def test_start_use_console(captured, monkeypatch, env, args, expected):
    if env is not None:
        monkeypatch.setenv("RTEMS_USE_CONSOLE", env)
    reload_globals()
    result = CliRunner().invoke(main_mod.cli, ["start", "--no-copy", *args])
    assert result.exit_code == 0, result.output
    assert captured["host_and_port"] == "BL19I-VA-IOC-01"
    assert captured["use_console"] is expected


def test_telnet_command_modes():
    assert TelnetRTEMS("host:7002").command == "telnet host 7002"
    assert (
        TelnetRTEMS("BL19I-VA-IOC-01", use_console=True).command
        == "console BL19I-VA-IOC-01"
    )


def test_globals_default_no_console(monkeypatch):
    monkeypatch.delenv("RTEMS_USE_CONSOLE", raising=False)
    reload_globals()
    assert GLOBALS.RTEMS_USE_CONSOLE is False
