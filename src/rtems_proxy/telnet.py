import signal
import sys
from enum import Enum
from time import sleep

import pexpect

from .utils import run_command


class CannotConnectError(Exception):
    pass


class RtemsState(Enum):
    MOT = 0
    IOC = 2
    UNKNOWN = 3


class TelnetRTEMS:
    """
    A class for connecting to an RTEMS MVME5500 IOC over telnet.

    properties:
    _hostname: the hostname of the terminal server connected to the IOC
    _port: the port of the terminal server connected to the IOC
    _ioc_reboot: a flag to determine if the IOC should be rebooted
    _child: the pexpect child object for the initial telnet session
    """

    MOT_PROMPT = "MVME5500> $"
    CONTINUE = "<SPC> to Continue"
    REBOOTED = "TCP Statistics"
    IOC_STARTED = "iocRun: All initialization complete"
    IOC_CHECK = "\ntaskwdShow"
    IOC_RESPONSE = "free nodes"
    NO_CONNECTION = "Connection closed by foreign host"
    FAIL_STRINGS = ["Exception", "exception", "RTEMS_FATAL_SOURCE_EXCEPTION"]

    def __init__(
        self, host_and_port: str, ioc_reboot: bool = False, use_console: bool = False
    ):
        self._ioc_reboot = ioc_reboot
        self._child = None
        self._port = ""

        self.ioc_rebooted = False
        if use_console:
            # console needs no port
            self._hostname = host_and_port
            self.command = f"console {self._hostname}"
        else:
            self._hostname, self._port = host_and_port.split(":")
            self.command = f"telnet {self._hostname} {self._port}"

        signal.signal(signal.SIGINT, self.terminate)
        signal.signal(signal.SIGTERM, self.terminate)

    def terminate(self, signum, frame):
        """
        Allow the user to terminate the connection with ctrl-c while the
        pexpect child is running (but not once interactive telnet is started)
        """
        report("Terminating")
        exit(0)

    def connect(self):
        """
        connect to an IOC over telnet using pexpect and determine if we are
        at the bootloader or IOC shell. If we are at the bootloader, we will
        reboot the IOC into the IOC shell, we will also reboot if the ioc_reboot
        flag was set in the constructor.
        """
        self._child = pexpect.spawn(
            self.command,
            encoding="utf-8",
            logfile=sys.stdout,
            echo=False,
            codec_errors="ignore",
        )
        try:
            # first check for connection refusal
            self._child.expect(self.NO_CONNECTION, timeout=1)
        except pexpect.exceptions.TIMEOUT:
            # if we timeout looking for failed connection that is good
            pass
        else:
            report("Cannot connect to remote IOC, connection in use?")
            raise CannotConnectError

    def check_prompt(self, retries) -> RtemsState:
        """
        Determine if we are currently seeing an IOC shell prompt or
        bootloader. Because there is a possibility that we are in the middle
        of a reboot, we will retry for one before giving up.
        """
        assert self._child, "must call connect before check_prompt"

        for retry in range(retries):
            try:
                # see if we are in the IOC shell
                sleep(0.5)
                self._child.sendline(self.IOC_CHECK)
                self._child.expect(self.IOC_RESPONSE, timeout=1)
            except pexpect.exceptions.TIMEOUT:
                try:
                    # see if we are in the bootloader
                    self._child.sendline()
                    self._child.expect(self.MOT_PROMPT, timeout=1)
                except pexpect.exceptions.TIMEOUT:
                    # current state unknown. wait and retry
                    sleep(15)
                else:
                    report("Currently in bootloader")
                    return RtemsState.MOT
            else:
                report("Currently in IOC shell")
                return RtemsState.IOC

            report(f"Retry {retry + 1} of get current status")

        report("Current state UNKNOWN")
        raise CannotConnectError("Current state of remote IOC unknown")

    def reboot(self, into: RtemsState):
        """
        Reboot the board from IOC shell or bootloader and choose appropriate
        options to get to the state requested by the into argument.
        """
        assert self._child, "must call connect before reboot"

        report(f"Rebooting into {into.name}")
        current_state = self.check_prompt(retries=2)
        if current_state == RtemsState.MOT:
            self._child.sendline("reset")
        else:
            self._child.sendline("exit")

        self._child.expect(self.CONTINUE, timeout=30)
        if into == RtemsState.MOT:
            # send escape to get into the bootloader
            self._child.sendline(chr(27))
        else:
            # send space to boot the IOC
            self._child.send(" ")

    def get_epics_prompt(self, retries=5):
        """
        Get to the IOC shell prompt, if the IOC is not already running, reboot
        it into the IOC shell. If the IOC is running, do a reboot only if
        requested (in order to pick up new binaries/startup/epics db)
        """
        assert self._child, "must call connect before get_epics_prompt"

        current = self.check_prompt(retries=10)

        if current != RtemsState.IOC or (self._ioc_reboot and not self.ioc_rebooted):
            sleep(0.5)
            report("Rebooting the IOC")

            self.reboot(RtemsState.IOC)
            self.ioc_rebooted = True

            current = self.check_prompt(retries=10)
            if current != RtemsState.IOC:
                raise CannotConnectError("Failed to reboot into IOC shell")

    def get_boot_prompt(self):
        """
        Get to the bootloader prompt, if the IOC shell is running then exit
        and send appropriate commands to get to the bootloader
        """
        assert self._child, "must call connect before get_boot_prompt"

        current = self.check_prompt(retries=10)
        if current != RtemsState.MOT:
            # get out of the IOC and return to MOT
            self.reboot(RtemsState.MOT)
            self._child.expect(self.MOT_PROMPT, timeout=20)

        report("press enter for bootloader prompt")

    def sendline(self, command: str) -> None:
        """
        Send a command to the telnet session
        """
        assert self._child, "must call connect before send"
        self._child.sendline(command)

    def expect(self, pattern, timeout=10) -> None:
        """
        Expect a pattern in the telnet session
        """
        assert self._child, "must call connect before expect"
        self._child.expect(pattern, timeout=timeout)

    def flush_remaining_output(self) -> None:
        """
        Flush any remaining buffered output to stdout.
        Useful for displaying output before error reporting.
        """
        try:
            if self._child:
                self._child.read_nonblocking(size=8192, timeout=0.5)
        except (pexpect.exceptions.TIMEOUT, pexpect.exceptions.EOF):
            # no more output available, which is fine
            pass

    def close(self):
        if self._child:
            self._child.close()
            self._child = None

    def __del__(self):
        self.close()


def report(message):
    """
    print a message that is noticeable amongst all the other output
    """
    print(f"\n>>>> {message} <<<<\n")


def ioc_connect(
    host_and_port: str,
    reboot: bool = False,
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

        if reboot:
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
