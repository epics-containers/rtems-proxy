import os
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
from .connect import ioc_connect, motboot_connect, report
from .copy import check_new_version, copy_rtems, save_current_version
from .globals import GLOBALS, reload_globals
from .hybrid import hybrid_prepare

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


def _load_instance_env(instance_path: Path) -> tuple[dict[str, str], str]:
    """
    Extract environment variables from a services repo IOC instance folder.
    Sets them in os.environ and returns (env_vars, domain).

    Expects:
      instance_path/values.yaml        (instance-level env vars)
      instance_path/../values.yaml     (global env vars and domain)
    """
    global_values = instance_path.parent / "values.yaml"
    instance_values = instance_path / "values.yaml"

    if not global_values.exists():
        typer.echo(f"Global settings file {global_values} not found")
        raise typer.Exit(1)
    if not instance_values.exists():
        typer.echo(f"Instance settings file {instance_values} not found")
        raise typer.Exit(1)

    env_vars: dict[str, str] = {}

    with open(global_values) as fp:
        yaml = YAML(typ="safe").load(fp)
    try:
        domain = yaml["global"]["domain"]
    except KeyError:
        typer.echo(f"{global_values} global.domain key missing")
        raise typer.Exit(1) from None
    try:
        for item in yaml["global"]["env"]:
            env_vars[item["name"]] = str(item["value"])
    except KeyError:
        typer.echo(f"{global_values} global.env key missing")
        raise typer.Exit(1) from None

    with open(instance_values) as fp:
        yaml = YAML(typ="safe").load(fp)
    try:
        for item in yaml["ioc-instance"]["env"]:
            env_vars[item["name"]] = str(item["value"])
    except KeyError:
        typer.echo(f"{instance_values} ioc-instance.env key missing")
        raise typer.Exit(1) from None

    env_vars["IOC_DOMAIN"] = domain

    # IOC_NAME is the deployment/instance name, i.e. the services instance
    # folder name (and the helm release / k8s service name). It must NOT be
    # derived from IOC_ORIGINAL_LOCATION: that points at the legacy build
    # folder, whose basename can differ from the instance name (e.g.
    # bl-va-ioc-01 vs bl19i-va-ioc-01). Using the build folder name produced
    # the wrong TFTP boot path (/iocs/bl-va-ioc-01/rtems.ioc.bin), NFS mount
    # and rtems-client-name. The instance folder name is the authoritative
    # source, matching the $(IOC_NAME) subPathExpr volume mounts.
    env_vars["IOC_NAME"] = instance_path.name

    for name, value in env_vars.items():
        os.environ[name] = value

    return env_vars, domain


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
    configure: bool = typer.Option(
        True, "--configure/--no-configure", help="configure motBoot when rebooting"
    ),
    raise_errors: bool = typer.Option(
        True, "--raise-errors/--no-raise-errors", help="raise errors instead of exiting"
    ),
    hybrid: bool = typer.Option(
        False,
        "--hybrid/--no-hybrid",
        help="hybrid mode: generate runtime from ibek+msi before copying",
    ),
    instance: Path | None = typer.Option(
        None,
        help="path to IOC instance folder in a services repo "
        "(e.g. .../services/bl19i-va-ioc-01); "
        "extracts env vars from values.yaml so you don't have to export them",
        exists=True,
        file_okay=False,
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
    if instance:
        _load_instance_env(instance)
        reload_globals()

    report(
        f"Remote control startup of RTEMS IOC {GLOBALS.IOC_NAME}"
        f" at {GLOBALS.RTEMS_IOC_IP}"
    )
    if hybrid:
        hybrid_prepare(instance_path=instance)
    elif copy:
        copy_rtems()

    # always reboot if the IOC definition has changed
    if check_new_version():
        report("IOC definition has changed, forcing reboot to pick up changes")
        reboot = True

    if connect:
        assert GLOBALS.RTEMS_CONSOLE, "No RTEMS console defined"
        ioc_connect(
            GLOBALS.RTEMS_CONSOLE,
            reboot=reboot,
            attach=True,
            raise_errors=raise_errors,
            configure=configure,
        )
        # now we have rebooted into the IOC we can save the current version
        save_current_version()
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
    env_vars, domain = _load_instance_env(ioc_path)

    this_dir = Path(__file__).parent
    template = Path(this_dir / "rsync.sh.jinja").read_text()

    script = Template(template).render(
        env_vars=env_vars,
        domain=domain,
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
    dry_run: bool = typer.Option(
        False, help="print the configuration commands without applying them"
    ),
    use_console: bool = typer.Option(
        False, help="use conserver console instead of telnet"
    ),
):
    """
    Configure the RTEMS IOC boot parameters
    """

    if dry_run:
        config = Configure(None, debug=debug, dry_run=True)
        config.apply_settings()
    else:
        assert GLOBALS.RTEMS_CONSOLE, "No RTEMS console defined"

        telnet = motboot_connect(GLOBALS.RTEMS_CONSOLE, use_console=use_console)
        config = Configure(telnet, debug=debug, dry_run=False)
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
