from time import sleep

import pexpect

from .configure import Configure
from .telnet import CannotConnectError, RtemsState, TelnetRTEMS
from .utils import run_command


def report(message):
    """
    print a message that is noticeable amongst all the other output
    """
    print(f"\n>>>> {message} <<<<\n")


def ioc_connect(
    host_and_port: str,
    reboot: bool = False,
    configure: bool = True,
    attach: bool = True,
    raise_errors: bool = False,
):
    """
    Entrypoint to make a connection to an RTEMS IOC over telnet.
    Once connected, enters an interactive user session with the IOC.

    args:
    host_and_port: 'hostname:port' of the IOC to connect to
    reboot: reboot the IOC to pick up new binaries/startup/epics db
    """
    telnet = TelnetRTEMS(host_and_port, reboot)

    try:
        telnet.connect()

        # this will untangle a partially executed gevEdit command
        for _ in range(3):
            telnet.sendline("\r")

        current = telnet.check_prompt(retries=6, timeout=10)
        match current:
            case RtemsState.MOT:
                report("At MOTBoot prompt")
                reboot = True
            case RtemsState.UNKNOWN:
                report("Current IOC state unknown, attempting reboot ...")
                reboot = True
            case RtemsState.IOC:
                report("At IOC shell prompt")

        if reboot:
            if configure:
                report("Rebooting to configure motBoot settings")
                telnet.get_boot_prompt(retries=10)
                sleep(1)
                cfg = Configure(telnet)
                cfg.apply_settings()
            else:
                report("Rebooting into IOC shell")

            telnet.get_epics_prompt(retries=10)
        else:
            report("Auto reboot disabled. Skipping reboot")

    except (CannotConnectError, pexpect.exceptions.TIMEOUT):
        report("Connection failed, Exiting.")
        telnet.close()
        raise

    except Exception as e:
        # flush any remaining buffered output to stdout
        telnet.flush_remaining_output()
        report(f"An error occurred: {e}")
        telnet.close()
        if raise_errors:
            raise

    telnet.close()
    if attach:
        report("Connecting to IOC console, hit enter for a prompt")
        run_command(telnet.command)


def motboot_connect(
    host_and_port: str, reboot: bool = False, use_console: bool = False
) -> TelnetRTEMS:
    """
    Connect to the MOTBoot bootloader prompt, rebooting if needed.

    Returns a TelnetRTEMS object that is connected to the MOTBoot bootloader
    """
    telnet = TelnetRTEMS(host_and_port, ioc_reboot=reboot, use_console=use_console)
    telnet.connect()

    # this will untangle a partially executed gevEdit command
    for _ in range(3):
        telnet.sendline("\r")

    telnet.get_boot_prompt()

    return telnet
