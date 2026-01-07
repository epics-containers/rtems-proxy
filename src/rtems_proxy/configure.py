"""
Class to apply MOTBoot configuration to a VME crate.
"""

from time import sleep

from .globals import GLOBALS
from .telnet import TelnetRTEMS


class Configure:
    def __init__(self, telnet: TelnetRTEMS, debug: bool = False):
        self.telnet = telnet
        self.debug = debug

    def apply_nvm(self, variable: str, value: str):
        self.telnet.sendline(f"gevE {variable}")
        self.telnet.expect(r"\(Blank line terminates input.\)")
        self.telnet.sendline(value + "\r")
        self.telnet.sendline("\r")
        self.telnet.expect(r"\?")
        self.telnet.sendline("Y\r")

    def apply_settings(self):
        for v in [
            GLOBALS.RTEMS_IOC_NETMASK,
            GLOBALS.RTEMS_IOC_GATEWAY,
            GLOBALS.RTEMS_IOC_IP,
            GLOBALS.RTEMS_NFS_IP,
            GLOBALS.RTEMS_TFTP_IP,
        ]:
            if v is None or v == "":
                raise ValueError(
                    "RTEMS_IOC_NETMASK, RTEMS_IOC_GATEWAY, RTEMS_IOC_IP, "
                    "RTEMS_NFS_IP, and RTEMS_TFTP_IP must be set"
                )

        ioc_bin = "ioc" if self.debug else "ioc.boot"

        if GLOBALS.RTEMS_EPICS_NFS_MOUNT:
            nfs_mount = GLOBALS.RTEMS_EPICS_NFS_MOUNT
        else:
            nfs_mount = f"{GLOBALS.RTEMS_NFS_IP}:/iocs/{GLOBALS.IOC_NAME}:/epics"

        if GLOBALS.RTEMS_EPICS_SCRIPT:
            epics_script = GLOBALS.RTEMS_EPICS_SCRIPT
        else:
            epics_script = "/epics/runtime/st.cmd"

        if GLOBALS.RTEMS_EPICS_BINARY:
            epics_binary = GLOBALS.RTEMS_EPICS_BINARY
        else:
            epics_binary = f"{GLOBALS.IOC_NAME.lower()}/ioc/bin/RTEMS-beatnik/{ioc_bin}"

        mot_boot = (
            f"dla=malloc 0x4000000\r"
            f"tftpGet -d/dev/enet1"
            f" -f{epics_binary}"
            f" -m{GLOBALS.RTEMS_IOC_NETMASK}"
            f" -g{GLOBALS.RTEMS_IOC_GATEWAY}"
            f" -s{GLOBALS.RTEMS_TFTP_IP}"
            f" -c{GLOBALS.RTEMS_IOC_IP}"
            f" -adla -r3 -v\r"
            f"go -a04000000\r"
            f"reset"
        )

        if GLOBALS.RTEMS_EPICS_NTP_SERVER:
            self.apply_nvm("epics-ntpserver", GLOBALS.RTEMS_EPICS_NTP_SERVER)

        # These checks were performed above, so we can safely assert non-None
        assert GLOBALS.RTEMS_IOC_NETMASK is not None
        assert GLOBALS.RTEMS_IOC_GATEWAY is not None
        assert GLOBALS.RTEMS_NFS_IP is not None
        assert GLOBALS.RTEMS_IOC_IP is not None

        self.apply_nvm("mot-/dev/enet0-snma", GLOBALS.RTEMS_IOC_NETMASK)
        self.apply_nvm("mot-/dev/enet0-gipa", GLOBALS.RTEMS_IOC_GATEWAY)
        self.apply_nvm("mot-/dev/enet0-sipa", GLOBALS.RTEMS_NFS_IP)
        self.apply_nvm("mot-/dev/enet0-cipa", GLOBALS.RTEMS_IOC_IP)
        self.apply_nvm("mot-boot-device", "/dev/em1")
        self.apply_nvm("mot-script-boot", mot_boot)
        self.apply_nvm("rtems-client-name", GLOBALS.IOC_NAME)
        self.apply_nvm("epics-script", epics_script)
        self.apply_nvm("epics-nfsmount", nfs_mount)
        # self.apply_nvm_variable("epics-ntpserver", "EPICS_TS_NTP_INET")
        self.apply_nvm("mot-/dev/enet0-snma", GLOBALS.RTEMS_IOC_NETMASK)

        sleep(1)
