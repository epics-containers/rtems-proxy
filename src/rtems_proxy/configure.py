"""
Class to apply MOTBoot configuration to a VME crate.
"""

from time import sleep

from .globals import GLOBALS
from .telnet import TelnetRTEMS


class Configure:
    def __init__(
        self, telnet: TelnetRTEMS | None, debug: bool = False, dry_run: bool = False
    ):
        self.telnet = telnet
        self.debug = debug
        self.dry_run = dry_run
        if dry_run:
            self.cr = "\n  "
        else:
            self.cr = "\r"

    def apply_nvm(self, variable: str, value: str | None):
        if self.dry_run:
            print(f"{variable}={value}")
            return

        assert self.telnet is not None, (
            "Telnet connection is required to apply settings"
        )
        if value is None or value == "":
            self.telnet.sendline(f"gevDel {variable}")
            self.telnet.expect(r"\?")
            self.telnet.sendline("Y")
        else:
            self.telnet.sendline(f"gevE {variable}")
            self.telnet.expect(r"\(Blank line terminates input.\)")
            self.telnet.sendline(value)
            self.telnet.sendline("")
            self.telnet.expect(r"\?")
            self.telnet.sendline("Y")

    def apply_settings(self):
        if not self.dry_run:
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

        mot_boot = (
            f"dla=malloc 0x4000000{self.cr}"
            f"tftpGet -d/dev/enet1"
            f" -f{GLOBALS.RTEMS_EPICS_BINARY}"
            f" -m{GLOBALS.RTEMS_IOC_NETMASK}"
            f" -g{GLOBALS.RTEMS_IOC_GATEWAY}"
            f" -s{GLOBALS.RTEMS_TFTP_IP}"
            f" -c{GLOBALS.RTEMS_IOC_IP}"
            f" -adla -r3 -v{self.cr}"
            f"go -a04000000{self.cr}"
            f"reset"
        )

        self.apply_nvm("mot-/dev/enet0-cipa", GLOBALS.RTEMS_IOC_IP)
        self.apply_nvm("mot-/dev/enet0-snma", GLOBALS.RTEMS_IOC_NETMASK)
        self.apply_nvm("mot-/dev/enet0-gipa", GLOBALS.RTEMS_IOC_GATEWAY)
        self.apply_nvm("mot-/dev/enet0-sipa", GLOBALS.RTEMS_NFS_IP)
        self.apply_nvm("mot-boot-device", "/dev/em1")
        self.apply_nvm("mot-script-boot", mot_boot)
        self.apply_nvm("rtems-client-name", GLOBALS.IOC_NAME)
        self.apply_nvm("epics-script", GLOBALS.RTEMS_EPICS_SCRIPT)

        if GLOBALS.RTEMS_EPICS_NFS_MOUNT:
            self.apply_nvm(
                "epics-nfsmount",
                f"{GLOBALS.RTEMS_NFS_IP}:"
                f"{GLOBALS.RTEMS_EPICS_NFS_MOUNT}/{GLOBALS.IOC_NAME.lower()}:"
                f"{GLOBALS.RTEMS_NFS_ROOT_PATH}",
            )

        if GLOBALS.RTEMS_EPICS_NTP_SERVER:
            self.apply_nvm("epics-ntpserver", GLOBALS.RTEMS_EPICS_NTP_SERVER)

        sleep(1)
