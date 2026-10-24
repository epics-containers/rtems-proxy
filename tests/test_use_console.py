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
def clean_env(monkeypatch):
    """Start with RTEMS_USE_CONSOLE unset; restore env and GLOBALS afterwards."""
    monkeypatch.delenv("RTEMS_USE_CONSOLE", raising=False)
    monkeypatch.delenv("RTEMS_CONSOLE_COMMAND", raising=False)
    yield monkeypatch
    monkeypatch.undo()  # restore the original environment first
    reload_globals()  # then rebuild GLOBALS from it


@pytest.fixture
def captured(clean_env):
    monkeypatch = clean_env
    calls: dict = {}

    def fake_ioc_connect(host_and_port, **kwargs):
        calls["host_and_port"] = host_and_port
        calls.update(kwargs)

    monkeypatch.setattr(main_mod, "ioc_connect", fake_ioc_connect)
    monkeypatch.setattr(main_mod, "check_new_version", lambda: False)
    monkeypatch.setattr(main_mod, "save_current_version", lambda: None)
    monkeypatch.setenv("RTEMS_CONSOLE", "BL19I-VA-IOC-01")
    return calls


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
def test_start_use_console(captured, clean_env, env, args, expected):
    if env is not None:
        clean_env.setenv("RTEMS_USE_CONSOLE", env)
    reload_globals()
    result = CliRunner().invoke(main_mod.cli, ["start", "--no-copy", *args])
    assert result.exit_code == 0, result.output
    assert captured["host_and_port"] == "BL19I-VA-IOC-01"
    assert captured["use_console"] is expected


USE_CONSOLE_CASES = [
    (None, [], False),
    (None, ["--use-console"], True),
    ("true", [], True),
    ("1", ["--no-use-console"], False),
    ("false", [], False),
]


@pytest.mark.parametrize("env, args, expected", USE_CONSOLE_CASES)
def test_configure_use_console(clean_env, env, args, expected):
    calls: dict = {}

    class FakeTelnet:
        command = "fake"

        def close(self):
            pass

    def fake_motboot_connect(host_and_port, **kwargs):
        calls["host_and_port"] = host_and_port
        calls.update(kwargs)
        return FakeTelnet()

    class FakeConfigure:
        def __init__(self, *args, **kwargs):
            pass

        def apply_settings(self):
            pass

    clean_env.setattr(main_mod, "motboot_connect", fake_motboot_connect)
    clean_env.setattr(main_mod, "Configure", FakeConfigure)
    clean_env.setenv("RTEMS_CONSOLE", "BL19I-VA-IOC-01")
    if env is not None:
        clean_env.setenv("RTEMS_USE_CONSOLE", env)
    reload_globals()
    result = CliRunner().invoke(main_mod.cli, ["configure", *args])
    assert result.exit_code == 0, result.output
    assert calls["host_and_port"] == "BL19I-VA-IOC-01"
    assert calls["use_console"] is expected


@pytest.mark.parametrize("env, args, expected", USE_CONSOLE_CASES)
def test_stress_use_console(captured, clean_env, env, args, expected):
    # make the first reboot "fail" so the stress loop exits
    def fake_ioc_connect(host_and_port, **kwargs):
        captured["host_and_port"] = host_and_port
        captured.update(kwargs)
        raise RuntimeError("stop")

    clean_env.setattr(main_mod, "ioc_connect", fake_ioc_connect)
    if env is not None:
        clean_env.setenv("RTEMS_USE_CONSOLE", env)
    reload_globals()
    CliRunner().invoke(main_mod.cli, ["stress", *args])
    assert captured["host_and_port"] == "BL19I-VA-IOC-01"
    assert captured["use_console"] is expected


def test_telnet_command_modes(clean_env):
    reload_globals()
    assert TelnetRTEMS("host:7002").command == "telnet host 7002"
    # absolute path by default: stdio-socket's 'console' script is on PATH first
    assert (
        TelnetRTEMS("BL19I-VA-IOC-01", use_console=True).command
        == "/usr/bin/console BL19I-VA-IOC-01"
    )


def test_console_command_override(clean_env):
    clean_env.setenv("RTEMS_CONSOLE_COMMAND", "/usr/bin/console -M cs-master")
    reload_globals()
    assert (
        TelnetRTEMS("BL19I-VA-IOC-01", use_console=True).command
        == "/usr/bin/console -M cs-master BL19I-VA-IOC-01"
    )


def test_globals_default_no_console(clean_env):
    reload_globals()
    assert GLOBALS.RTEMS_USE_CONSOLE is False
