from datetime import datetime
from pathlib import Path
from time import sleep

import typer
from jinja2 import Template
from ruamel.yaml import YAML

from rtems_proxy.trace import parse_stack_trace
from rtems_proxy.utils import run_command

from . import __version__
from .configure import Configure
from .copy import copy_rtems
from .globals import GLOBALS
from .telnet import ioc_connect, motboot_connect, report

__all__ = ["main"]

cli = typer.Typer()


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@cli.callback()
def main(
    version: bool | None = typer.Option(
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
    connect: bool = typer.Option(
        True, "--connect/--no-connect", help="connect to the IOC console"
    ),
    reboot: bool = typer.Option(
        True, "--reboot/--no-reboot", help="reboot the IOC first"
    ),
    raise_errors: bool = typer.Option(
        True, "--raise-errors/--no-raise-errors", help="raise errors instead of exiting"
    ),
):
    """
    Starts an RTEMS IOC. Places the IOC binaries in the expected location,
    restarts the IOC and connects stdio to the IOC console.

    This should be called inside of a runtime IOC container after ibek
    has generated the runtime assets for the IOC.

    The standard 'start.sh' in the runtime IOC will call this entry point if
    it detects that EPICS_HOST_ARCH==RTEMS-beatnik

    args:
    copy:    Copy the RTEMS binaries to the IOCs TFTP and NFS directories first
    connect: Connect to the IOC console after rebooting
    reboot:  Reboot the IOC once the binaries are copied and the connection is
             made. Ignored if connect is False.
    """
    report(
        f"Remote control startup of RTEMS IOC {GLOBALS.IOC_NAME}"
        f" at {GLOBALS.RTEMS_IOC_IP}"
    )
    if copy:
        copy_rtems()
    if connect:
        assert GLOBALS.RTEMS_CONSOLE, "No RTEMS console defined"
        ioc_connect(
            GLOBALS.RTEMS_CONSOLE, reboot=reboot, attach=True, raise_errors=raise_errors
        )
    else:
        report("IOC console connection disabled. ")


@cli.command()
def dev(
    ioc_repo: Path = typer.Argument(
        ...,
        help="The beamline/accelerator repo holding the IOC instance",
        file_okay=False,
        exists=True,
    ),
    ioc_name: str = typer.Argument(
        ...,
        help="The name of the IOC instance to work on",
    ),
):
    """
    Sets up a devcontainer to work on an IOC instance. Must be run from within
    the developer container for the generic IOC that the instance uses.

    args:
    ioc_repo: The path to the IOC repository that holds the instance
    ioc_name: The name of the IOC instance to work on
    """

    ioc_path = ioc_repo / "services" / ioc_name

    values = ioc_repo / "services" / "values.yaml"
    if not values.exists():
        typer.echo(f"Global settings file {values} not found. Exiting")
        raise typer.Exit(1)

    ioc_values = ioc_path / "values.yaml"
    if not ioc_values.exists():
        typer.echo(f"Instance settings file {ioc_values} not found. Exiting")
        raise typer.Exit(1)

    env_vars = {}
    # TODO in future use pydantic and make a model for this but for now let's cheese it.
    with open(values) as fp:
        yaml = YAML(typ="safe").load(fp)
    try:
        ioc_group = yaml["global"]["ioc_group"]
    except KeyError:
        typer.echo(f"{values} global.ioc_group key missing")
        raise typer.Exit(1) from None
    try:
        ioc_group = yaml["global"]["ioc_group"]
        for item in yaml["ioc-instance"]["globalEnv"]:
            env_vars[item["name"]] = item["value"]
    except KeyError:
        typer.echo(f"{values} globalEnv key missing")
        raise typer.Exit(1) from None

    with open(ioc_values) as fp:
        yaml = YAML(typ="safe").load(fp)
    try:
        for item in yaml["ioc-instance"]["iocEnv"]:
            env_vars[item["name"]] = item["value"]
    except KeyError:
        typer.echo(f"{ioc_values} iocEnv key missing")
        raise typer.Exit(1) from None

    this_dir = Path(__file__).parent
    template = Path(this_dir / "rsync.sh.jinja").read_text()

    script = Template(template).render(
        env_vars=env_vars,
        ioc_group=ioc_group,
        ioc_name=ioc_name,
        ioc_path=ioc_path,
    )

    script_file = Path("/tmp/dev_proxy.sh")
    script_file.write_text(script)

    typer.echo(f"\nIOC {ioc_name} dev environment prepared for {ioc_repo}")
    typer.echo("You can now change and compile support module or iocs.")
    typer.echo("Then start the ioc with '/epics/ioc/start.sh'")
    typer.echo(f"\n\nPlease first source {script_file} to set up the dev environment.")


@cli.command()
def configure(
    debug: bool = typer.Option(False, help="use debug ioc binary"),
    attach: bool = typer.Option(
        False, help="attach to the IOC console after configuration"
    ),
    use_console: bool = typer.Option(
        False, help="use conserver console instead of telnet"
    ),
):
    """
    Configure the RTEMS IOC boot parameters
    """

    assert GLOBALS.RTEMS_CONSOLE, "No RTEMS console defined"
    telnet = motboot_connect(GLOBALS.RTEMS_CONSOLE, use_console=use_console)
    config = Configure(telnet, debug)
    config.apply_settings()
    telnet.close()
    if attach:
        run_command(telnet.command)


@cli.command()
def stress():
    """
    Stress test the IOC by constantly rebooting and checking for failed boot

    Aborts and prints the time when a failed boot is detected
    """
    if not GLOBALS.RTEMS_CONSOLE:
        raise ValueError("RTEMS_CONSOLE must be set")

    tries = 0
    try:
        while True:
            tries += 1
            print(f">>>>>> REBOOT ATTEMPT {tries} <<<<<<<")
            ioc_connect(
                GLOBALS.RTEMS_CONSOLE, reboot=True, attach=False, raise_errors=True
            )
            sleep(5)
    except Exception as e:
        msg = f"\n\nIOC boot number {tries} failed at {datetime.now()}.\n\n"
        raise RuntimeError(msg) from e


@cli.command()
def trace(
    trace_file: Path = typer.Argument(
        ...,
        help="The path to the file containing the stack trace",
        file_okay=True,
        exists=True,
    ),
):
    """
    Parse a stack trace from a RTEMS failure
    """
    trace = trace_file.read_text()
    parse_stack_trace(trace)


if __name__ == "__main__":
    cli()
