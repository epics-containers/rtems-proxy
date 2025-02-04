from pathlib import Path

import typer
from jinja2 import Template
from ruamel.yaml import YAML

from . import __version__
from .copy import copy_rtems
from .globals import GLOBALS
from .telnet import ioc_connect, report

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
        ioc_connect(GLOBALS.RTEMS_CONSOLE, reboot=reboot)
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


# test with:
#     pipenv run python -m ibek


if __name__ == "__main__":
    cli()
