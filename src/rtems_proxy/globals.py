"""
A few global definitions
"""

import os
from pathlib import Path


class _Globals:
    """Helper class for accessing global constants."""

    def __init__(self) -> None:
        ########################################################################
        ## Constants
        ########################################################################

        self.RTEMS_BINARY_DEFAULT_NAME = "rtems.ioc.bin"
        self.RTEMS_SCRIPT_DEFAULT_NAME = "st.cmd"

        self.RTEMS_TFTP_ROOT_PATH = Path("/ioc_tftp")
        """ root folder of a mounted PVC in which to place IOC binaries """
        self.RTEMS_NFS_ROOT_PATH = Path("/ioc_nfs")
        """ root folder of a mounted NFS folder in which to place IOC runtime files """

        ########################################################################
        ## Values relating to IOCs built inside containers using ioc-template
        ########################################################################

        self.EPICS_ROOT = Path(os.getenv("EPICS_ROOT", "/epics/"))
        """Root of epics directory tree"""

        self.SUPPORT = Path(os.getenv("SUPPORT", self.EPICS_ROOT / "support"))
        """ The root folder for support modules """

        self.RUNTIME = self.EPICS_ROOT / "runtime"

        self.EPICS_HOST_ARCH = os.getenv("EPICS_HOST_ARCH", "linux-x86_64")
        """ Host architecture """

        self.EPICS_TARGET_ARCH = os.getenv("EPICS_TARGET_ARCH", "RTEMS-beatnik")
        """ Cross compilation target architecture """

        ########################################################################
        ## Beamline level config from global.env in services/values.yaml
        ########################################################################

        self.RTEMS_IOC_GATEWAY = os.getenv("RTEMS_IOC_GATEWAY")
        """ gateway address for the RTEMS IOC hardware """

        self.RTEMS_IOC_NETMASK = os.getenv("RTEMS_IOC_NETMASK")
        """ netmask for the real RTEMS IOC hardware """

        self.RTEMS_NFS_IP = os.getenv("RTEMS_NFS_IP")
        """ address of an NFS server that the RTEMS IOC can access """

        self.RTEMS_TFTP_IP = os.getenv("RTEMS_TFTP_IP")
        """ address of a TFTP server that the RTEMS IOC can access """

        self.RTEMS_EPICS_NTP_SERVER = os.getenv("RTEMS_EPICS_NTP_SERVER")
        """ ip address for the ntp server """

        self.RTEMS_EPICS_NFS_MOUNT = os.getenv("RTEMS_EPICS_NFS_MOUNT")
        """ NFS mount point for the EPICS IOC """

        ########################################################################
        ## IOC instance config from ioc-instance.env in
        ## services/ioc_name/values.yaml
        ## these MUST be set for each RTEMS IOC instance
        ########################################################################

        self.RTEMS_IOC_IP = os.getenv("RTEMS_IOC_IP")
        """ address of the real RTEMS IOC  hardware """

        self.RTEMS_CONSOLE = os.getenv("RTEMS_CONSOLE")
        """ address:port to connect to the IOC console """

        self.IOC_ORIGINAL_LOCATION = Path(
            os.getenv("IOC_ORIGINAL_LOCATION", self.EPICS_ROOT / "ioc")
        )
        """ The root folder to get IOC source and binaries from
            for legacy built IOCs, set to an IOC folder in prod or work
            for in-container (ibek) built IOCs /epics/ioc is the default
        """

        ########################################################################
        ## IOC instance config (defaults are normally sufficient)
        ########################################################################

        self.IOC_NAME = os.getenv("IOC_NAME", "NO_IOC_NAME")
        """ the lowercase name of this IOC (derived from the instance folder name) """

        self.RTEMS_EPICS_SCRIPT = os.getenv("RTEMS_EPICS_SCRIPT", "/ioc_nfs/st.cmd")
        """ override for the standard EPICS startup script filename """

        self.RTEMS_EPICS_BINARY = os.getenv(
            "RTEMS_EPICS_BINARY",
            f"/iocs/{self.IOC_NAME.lower()}/{self.RTEMS_BINARY_DEFAULT_NAME}",
        )
        """ override for the standard EPICS RTEMS binary TFTP file path """


GLOBALS = _Globals()
