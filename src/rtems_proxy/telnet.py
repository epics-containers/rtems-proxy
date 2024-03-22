import signal
import sys
from enum import Enum
from time import sleep

import pexpect

from .utils import run_command


class CurrentPrompt(Enum):
    MOT = 0
    IOC = 2
    UNKNOWN = 3


class TelnetRTEMS:
    MOT_PROMPT = "MVME5500> "
    CONTINUE = "<SPC> to Continue"
    REBOOTING = "(most recent call last):"
    REBOOTED = "TCP Statistics"
    IOC_STARTED = "iocRun: All initialization complete"
    DBPF = "help dbpf"
    DBPF_RESPONSE = "of record field."
    NO_CONNECTION = "Connection closed by foreign host"

    def __init__(self, host_and_port: str, reboot: bool, pause: bool):
        self.hostname, self.port = host_and_port.split(":")
        self.reboot = reboot
        self.pause = pause
        self.running = True
        self.terminated = False
        self.command = f"telnet {self.hostname} {self.port}"
        signal.signal(signal.SIGINT, self.terminate)
        signal.signal(signal.SIGTERM, self.terminate)

    def terminate(self, signum, frame):
        print(">> Terminating <<")
        exit(0)

    def check_prompt(self, child, retries=30) -> CurrentPrompt:
        while retries > 0:
            try:
                child.sendline()
                child.expect(self.MOT_PROMPT, timeout=1)
            except pexpect.exceptions.TIMEOUT:
                child.sendline(self.DBPF)
                try:
                    child.expect(self.DBPF_RESPONSE, timeout=1)
                except pexpect.exceptions.TIMEOUT:
                    sleep(2)
                else:
                    print("\n>> Currently in IOC shell <<\n")
                    return CurrentPrompt.IOC
            else:
                print("\n>>> Currently in bootloader <<\n")
                return CurrentPrompt.MOT
            print(">> Retrying get current status ... <<")
            retries -= 1

        print("\n>> Current state UNKNOWN <<\n")
        raise RuntimeError("Current state of remote IOC unknown")

    def get_epics_prompt(self, child):
        current = self.check_prompt(child)
        if current != CurrentPrompt.IOC:
            sleep(0.2)
            child.send("reset\n")
            child.expect(self.CONTINUE, timeout=10)

            child.send(" ")
            child.expect(self.IOC_STARTED, timeout=50)

        print(">> press enter for IOC shell prompt <<")

    def get_boot_prompt(self, child):
        current = self.check_prompt(child)
        if current != CurrentPrompt.MOT:
            # get out of the IOC and return to MOT
            child.sendline("exit")
            try:
                child.expect(self.REBOOTING, timeout=1)
            except UnicodeDecodeError:
                pass  # there are illegal chars during the reboot process
            child.expect(self.CONTINUE, timeout=10)

            child.send(chr(27))
            child.expect(self.MOT_PROMPT, timeout=20)

        print(">> press enter for bootloader prompt <<")


def connect(host_and_port: str, reboot: bool = False, pause: bool = False):
    telnet = TelnetRTEMS(host_and_port, reboot, pause)

    child = pexpect.spawn(
        telnet.command, encoding="utf-8", logfile=sys.stdout, echo=False
    )
    try:
        child.expect(telnet.NO_CONNECTION, timeout=1)
    except pexpect.exceptions.TIMEOUT:
        pass
    else:
        print(">> Cannot connect to remote IOC, connection in use? <<")
        child.close()
        return

    telnet.get_epics_prompt(child)

    # telnet.get_boot_prompt(child)

    child.close()

    run_command(telnet.command)
