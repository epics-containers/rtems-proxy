from time import sleep
from typing import Optional

import typer

from . import __version__
from .copy import copy_rtems
from .globals import GLOBALS
from .telnet import connect

__all__ = ["main"]

cli = typer.Typer()


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@cli.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Print the version of ibek and exit",
    ),
):
    """
    Proxy for RTEMS IOCs controlling and monitoring
    """


@cli.command()
def start(
    copy: bool = typer.Option(
        True, "--copy/--no-copy", help="copy binaries before connecting"
    ),
    reboot: bool = typer.Option(
        True, "--reboot/--no-reboot", help="reboot the IOC first"
    ),
):
    """
    Start the RTEMS IOC
    """
    print(
        f"Remote control startup of RTEMS IOC {GLOBALS.IOC_NAME}"
        f" at {GLOBALS.RTEMS_IOC_IP}"
    )
    if copy:
        copy_rtems()
    connect(GLOBALS.RTEMS_CONSOLE, reboot=reboot)

    while True:
        print(f"\n\nIOC {GLOBALS.IOC_NAME} disconnected. Reconnect or exit? [r/e]")
        choice = ""
        while choice not in ["r", "e"]:
            choice = input()
        if choice == "e":
            break
        connect(GLOBALS.RTEMS_CONSOLE)
        sleep(10)


# test with:
#     pipenv run python -m ibek
if __name__ == "__main__":
    cli()
