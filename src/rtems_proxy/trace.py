"""
Some functions to interpret a stack trace from a RTEMS failure
"""

import re

from .globals import GLOBALS
from .utils import run_command

IP = re.compile(r"Stack Trace:\n *IP: *(0x[0-9a-f]*)")
STACK = re.compile(r"--\^ (0x[0-9a-f]*)")
symbols = GLOBALS.IOC / "bin" / "RTEMS-beatnik" / "ioc"


def parse_stack_trace(trace: str):
    """
    Parse a stack trace from a RTEMS failure

    Args:
        trace (str): log containing a stack trace
    """
    ip = IP.findall(trace)
    addrs = STACK.findall(trace)

    print(f"IP: {ip[0]}\nStack {addrs}")

    if len(ip) == 0 or len(addrs) == 0:
        raise ValueError("Could not find a stack trace in the log")
    elif len(ip) > 1:
        raise ValueError("Multiple stack traces in the log")

    addrs.reverse()
    for addr in addrs:
        run_command(f"rtems-addr2line {addr} -e {symbols}")
    run_command(f"rtems-addr2line {ip[0]} -e {symbols}")
