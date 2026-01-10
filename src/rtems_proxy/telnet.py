import signal
import sys
from enum import Enum
from time import sleep

import pexpect


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
            timeout=5,
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

    def check_prompt(self, retries, timeout=15) -> RtemsState:
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
                pass
            else:
                return RtemsState.IOC

            try:
                # see if we are in the bootloader
                self._child.sendline()
                self._child.expect(self.MOT_PROMPT, timeout=1)
            except pexpect.exceptions.TIMEOUT:
                pass
            else:
                return RtemsState.MOT

            try:
                # current state unknown. check for mot start prompt
                # in case we are in a boot loop
                self._child.expect(self.CONTINUE, timeout=timeout)
            except pexpect.exceptions.TIMEOUT:
                pass
            else:
                # send escape to get into the bootloader
                self._child.sendline(chr(27))
                return RtemsState.MOT

            report(f"Retry {retry + 1} of get current status")

        return RtemsState.UNKNOWN

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

        self.ioc_rebooted = True

    def get_epics_prompt(self, retries=5):
        """
        Get to the IOC shell prompt, if the IOC is not already running, reboot
        it into the IOC shell. If the IOC is running, do a reboot only if
        requested (in order to pick up new binaries/startup/epics db)
        """
        assert self._child, "must call connect before get_epics_prompt"

        current = self.check_prompt(retries=retries)

        if current != RtemsState.IOC or (self._ioc_reboot and not self.ioc_rebooted):
            sleep(0.5)

            report("Rebooting into IOC shell")
            self.reboot(RtemsState.IOC)

            current = self.check_prompt(retries=retries)
            if current != RtemsState.IOC:
                raise CannotConnectError("Failed to reboot into IOC shell")

    def get_boot_prompt(self, retries=5):
        """
        Get to the bootloader prompt, if the IOC shell is running then exit
        and send appropriate commands to get to the bootloader
        """
        assert self._child, "must call connect before get_boot_prompt"

        current = self.check_prompt(retries=retries)
        if current != RtemsState.MOT:
            # get out of the IOC and return to MOT
            self.reboot(RtemsState.MOT)
            self._child.expect(self.MOT_PROMPT, timeout=20)

        report("press enter for bootloader prompt")

    def sendline(self, command: str) -> None:
        """
        Send a command to the telnet session
        """
        # always pause a little to allow the previous expect to complete
        assert self._child, "must call connect before send"
        self._child.sendline(command + "\r")

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
