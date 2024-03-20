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
    root = GLOBALS.RTEMS_ROOT
    ioc_bins = (GLOBALS.IOC / "bin") / GLOBALS.EPICS_TARGET_ARCH
    bin_dest = root / "bin"

    # because we are moving the ioc files we need to fix up startup script paths
    startup = GLOBALS.RUNTIME / "st.cmd"
    cmd_txt = startup.read_text()
    cmd_txt = re.sub("/epics/", str(root), cmd_txt)
    startup.write_text(cmd_txt)

    # move all the files needed for runtime into the PVC that is being shared
    # over nfs/tftp by the nfsv2-tftp service
    shutil.copytree(GLOBALS.IOC, root / "ioc", symlinks=True, dirs_exist_ok=True)
    shutil.copytree(GLOBALS.RUNTIME, root / "runtime", dirs_exist_ok=True)
    Path.mkdir(bin_dest, exist_ok=True)
    shutil.move(ioc_bins / "ioc.boot", bin_dest)
