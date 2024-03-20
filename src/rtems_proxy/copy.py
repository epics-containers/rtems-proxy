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
    root = GLOBALS.RTEMS_ROOT
    # root of the path that the RTEMS IOC expects to find the IOC files
    rtems_root = Path("/iocs") / GLOBALS.IOC_GROUP / GLOBALS.IOC_NAME
    # the binary blob to load into the RTEMS IOC via TFTP
    ioc_bin = (GLOBALS.IOC / "bin") / GLOBALS.EPICS_TARGET_ARCH / "ioc.boot"
    # where to copy the Generic IOC folder to (at present only holds the dbd folder)
    dest_ioc = root / "ioc"

    # because we are moving the ioc files we need to fix up startup script paths
    startup = GLOBALS.RUNTIME / "st.cmd"
    cmd_txt = startup.read_text()
    cmd_txt = re.sub("/epics/", f"{str(rtems_root)}/", cmd_txt)
    startup.write_text(cmd_txt)

    # move all the files needed for runtime into the PVC that is being shared
    # over nfs/tftp by the nfsv2-tftp service
    Path.mkdir(dest_ioc, exist_ok=True)
    shutil.copytree(GLOBALS.IOC / "dbd", dest_ioc, symlinks=True, dirs_exist_ok=True)
    shutil.copytree(GLOBALS.RUNTIME, root / "runtime", dirs_exist_ok=True)
    shutil.copy(ioc_bin, root)
