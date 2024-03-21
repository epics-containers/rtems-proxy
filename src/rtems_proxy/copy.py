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
    # where to copy the Generic IOC folder to (at present only holds the dbd folder)
    dest_ioc = root / "ioc"
    # where to copy the generated runtime assets to (st.cmd and ioc.db)
    dest_runtime = root / "runtime"

    # clean up previous IOC binaries
    shutil.rmtree(dest_ioc, ignore_errors=True)
    shutil.rmtree(dest_runtime, ignore_errors=True)

    # move all the files needed for runtime into the PVC that is being shared
    # over nfs/tftp by the nfsv2-tftp service
    Path.mkdir(dest_ioc, exist_ok=True)
    shutil.copytree(GLOBALS.IOC / "dbd", dest_ioc, symlinks=True, dirs_exist_ok=True)
    shutil.copytree(GLOBALS.RUNTIME, dest_runtime, dirs_exist_ok=True)

    # because we moved the ioc files we need to fix up startup script paths
    startup = dest_runtime / "st.cmd"
    cmd_txt = startup.read_text()
    cmd_txt = re.sub("/epics/", f"{str(rtems_root)}/", cmd_txt)
    startup.write_text(cmd_txt)
