"""
functions for moving IOC assets into position for a remote IOC to access
"""

import re
import shutil
from pathlib import Path

from .globals import GLOBALS


def copy_rtems():
    """
    Copy RTEMS binaries to a location where the RTEMS IOC can access them
    """
    # root of pvc mount into which we copy the IOC files for the RTEMS IOC to access
    root = GLOBALS.RTEMS_TFTP_PATH
    # root of the path that the RTEMS IOC expects to find the IOC files
    RTEMS_TFTP_PATH = Path("/iocs") / GLOBALS.IOC_GROUP / GLOBALS.IOC_NAME
    # where to copy the Generic IOC folder to (at present only holds the dbd folder)
    ioc_dest = root / "ioc"
    # where to copy the generated runtime assets to (st.cmd and ioc.db)
    dest_runtime = root / "runtime"

    # move all the files needed for runtime into the PVC that is being shared
    # over nfs/tftp by the nfsv2-tftp service
    ioc_src = GLOBALS.IOC.readlink()
    dbd_src = ioc_src / "dbd"
    dbd_dest = ioc_dest / "dbd"
    binary = Path("bin/RTEMS-beatnik/ioc.boot")
    bin_rtems_src = ioc_src / binary
    bin_rtems_dest = ioc_dest / binary
    bin_rtems_dest.parent.mkdir(parents=True, exist_ok=True)

    shutil.copytree(dbd_src, dbd_dest, symlinks=True, dirs_exist_ok=True)
    shutil.copy(bin_rtems_src, bin_rtems_dest)
    shutil.copytree(GLOBALS.RUNTIME, dest_runtime, dirs_exist_ok=True)

    # because we moved the ioc files we need to fix up startup script paths
    startup = dest_runtime / "st.cmd"
    cmd_txt = startup.read_text()
    cmd_txt = re.sub("/epics/", f"{str(RTEMS_TFTP_PATH)}/", cmd_txt)
    startup.write_text(cmd_txt)
