"""
functions for moving IOC assets into position for a remote IOC to access
"""

import os
import subprocess
from pathlib import Path

from .globals import GLOBALS


def copy_rtems(debug: bool = False):
    """
    Copy RTEMS IOC binary and startup assets to a location where the RTEMS IOC
    can access them

    IMPORTANT: local_root and nfs_root are different perspectives on the same
               folder.
    nfs_root:   where the IOC files will be found from the perspective of a
                a client to the NFSv2 service. i.e. where the RTEMS crate
                will look for them using NFS.
    local_tftp_root:
                where the tftp_root folder is mounted into this rtems-proxy
                container. This is needed to copy the .boot files into place.
    """

    # TODO - this function is currently specific to legacy built IOCs
    # TODO - once IOCs are built in containers review this function to make it
    # TODO   work for both legacy and container built IOCs (it might just work?)

    local_tftp_root = GLOBALS.RTEMS_TFTP_PATH
    nfs_root = f"{GLOBALS.RTEMS_NFS_ROOT_PATH}/{GLOBALS.IOC_NAME.lower()}"
    sts = list(Path(GLOBALS.IOC_ORIGINAL_LOCATION).glob("bin/RTEMS-beatnik/st*"))
    if len(sts) == 0:
        raise FileNotFoundError(
            f"No RTEMS startup script found at "
            f"{GLOBALS.IOC_ORIGINAL_LOCATION}/bin/RTEMS-beatnik/st*"
        )
    ioc_script_name = sts[0].name

    # copy the IOC runtime files to the NFS root
    os.chdir(GLOBALS.IOC_ORIGINAL_LOCATION)
    subprocess.run(
        [
            "rsync",
            "--delete",
            "-r",
            "data",
            "db",
            "dbd",
            f"bin/RTEMS-beatnik/{ioc_script_name}",
            f"{nfs_root}",
        ],
        check=True,
    )

    # symlink the ioc start to a fixed name 'st.cmd'
    ioc_script_path = Path(nfs_root) / GLOBALS.RTEMS_SCRIPT_DEFAULT_NAME
    ioc_script_path.unlink(missing_ok=True)
    ioc_script_path.symlink_to(Path(nfs_root) / ioc_script_name)

    # TODO for container built IOCs the name will be ioc or ioc.boot
    if debug:
        ioc_bin = GLOBALS.IOC_NAME.upper()
    else:
        ioc_bin = f"{GLOBALS.IOC_NAME.upper()}.boot"

    # copy the .boot files to the TFTP root
    subprocess.run(
        [
            "rsync",
            "--delete",
            "/bin/RTEMS-beatnik/{ioc_bin}",
            f"{local_tftp_root}",
        ],
        check=True,
    )

    # symlink the ioc_bin to a fixed name 'rtems.ioc.boot' in the TFTP root
    tftp_ioc_boot = Path(local_tftp_root) / GLOBALS.RTEMS_BINARY_DEFAULT_NAME
    tftp_ioc_boot.unlink(missing_ok=True)
    tftp_ioc_boot.symlink_to(Path(local_tftp_root) / ioc_bin)
