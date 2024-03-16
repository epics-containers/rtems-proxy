import subprocess
import sys

from rtems_proxy import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "rtems_proxy", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
