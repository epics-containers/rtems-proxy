"""
A few global definitions
"""

import os
from pathlib import Path

DEFAULT_ARCH = "linux-x86_64"


class _Globals:
    """Helper class for accessing global constants."""

    def __init__(self) -> None:
        self.EPICS_ROOT = Path(os.getenv("EPICS_ROOT", "/epics/"))
        """Root of epics directory tree"""

        self.SUPPORT = Path(os.getenv("SUPPORT", self.EPICS_ROOT / "support"))
        """ The root folder for support modules """

        self.RUNTIME = self.EPICS_ROOT / "runtime"

        self.EPICS_HOST_ARCH = os.getenv("EPICS_HOST_ARCH", DEFAULT_ARCH)
        """ Host architecture """

        self.EPICS_TARGET_ARCH = os.getenv("EPICS_TARGET_ARCH", DEFAULT_ARCH)
        """ Cross compilation target architecture """

        self.IOC = Path(os.getenv("IOC", self.EPICS_ROOT / "ioc"))
        """ The root folder for IOC source and binaries """

        # TODO in future, shall we drop the RTEMS prefix and make this module
        # generic?

        self.RTEMS_ROOT = Path(os.getenv("RTEMS_ROOT", "/nfsv2-tftp"))
        """ root folder of a mounted PVC in which to place IOC binaries """

        self.RTEMS_IOC_IP = os.getenv("RTEMS_IOC_IP")
        """ address of the real RTEMS IOC  hardware """

        self.RTEMS_IOC_GATEWAY = os.getenv("RTEMS_IOC_GATEWAY")
        """ gateway address for the RTEMS IOC hardware """

        self.RTEMS_IOC_NETMASK = os.getenv("RTEMS_IOC_NETMASK")
        """ netmask for the real RTEMS IOC hardware """

        self.RTEMS_NFS_IP = os.getenv("RTEMS_NFS_IP")
        """ address of an NFS server that the RTEMS IOC can access """

        self.RTEMS_TFTP_IP = os.getenv("RTEMS_TFTP_IP")
        """ address of a TFTP server that the RTEMS IOC can access """

        self.RTEMS_CONSOLE = os.getenv("RTEMS_CONSOLE", "NO_CONSOLE")
        """ address:port to connect to the IOC console """

        self.IOC_NAME = os.getenv("IOC_NAME", "NO_IOC_NAME")
        """ the name of this IOC """

        self.IOC_GROUP = os.getenv("IOC_GROUP", "NO_IOC_GROUP")
        """ the name of the repository that this IOC is grouped into """


GLOBALS = _Globals()
