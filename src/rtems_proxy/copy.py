"""
functions for moving IOC assets into position for a remote IOC to access
"""

import os
import subprocess
from pathlib import Path

from .globals import GLOBALS


def save_current_version():
    """
    Save the current version string to a file in the NFS root so that the IOC
    can report its version on startup

    We use the env IOC_ORIGINAL_LOCATION as a proxy for the version string
    """
    version_file = Path(GLOBALS.RTEMS_NFS_ROOT_PATH) / "rtems_proxy_version.txt"
    with open(version_file, "w") as vf:
        vf.write(str(GLOBALS.IOC_ORIGINAL_LOCATION) + "\n")


def check_new_version():
    """
    Check if the version string saved in the NFS root matches the current
    version string.

    We use the env IOC_ORIGINAL_LOCATION as a proxy for the version string
    """
    version_file = Path(GLOBALS.RTEMS_NFS_ROOT_PATH) / "rtems_proxy_version.txt"
    if not version_file.exists():
        return True

    with open(version_file) as vf:
        saved_version = vf.read().strip()

    return saved_version != str(GLOBALS.IOC_ORIGINAL_LOCATION)


def copy_rtems(debug: bool = False):
    """
    Copy RTEMS IOC binary and startup assets to a location where the RTEMS IOC
    can access them
    """

    # TODO - this function is currently specific to legacy built IOCs
    # TODO - once IOCs are built in containers review this function to make it
    # TODO   work for both legacy and container built IOCs (it might just work?)

    # these represent where the rtems-proxy container mounts the IOC NFS and TFTP
    # shares
    local_tftp_root = GLOBALS.RTEMS_TFTP_ROOT_PATH
    local_nfs_root = f"{GLOBALS.RTEMS_NFS_ROOT_PATH}"

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
            f"{local_nfs_root}",
        ],
        check=True,
    )

    # symlink the ioc startup script to a fixed name 'st.cmd'
    ioc_script_path = Path(local_nfs_root) / GLOBALS.RTEMS_SCRIPT_DEFAULT_NAME
    ioc_script_path.unlink(missing_ok=True)
    ioc_script_path.symlink_to(Path(local_nfs_root) / ioc_script_name)

    # TODO for container built IOCs the name will be ioc or ioc.boot
    if debug:
        ioc_bin = GLOBALS.IOC_NAME.upper()
    else:
        ioc_bin = f"{GLOBALS.IOC_NAME.upper()}.boot"

    # copy the .boot files to the TFTP root
    subprocess.run(
        [
            "rsync",
            f"bin/RTEMS-beatnik/{ioc_bin}",
            f"{local_tftp_root}",
        ],
        check=True,
    )

    # move the ioc_bin to a fixed name 'rtems.ioc.bin' in the TFTP root
    tftp_ioc_boot = Path(local_tftp_root) / GLOBALS.RTEMS_BINARY_DEFAULT_NAME
    tftp_ioc_boot.unlink(missing_ok=True)
    (Path(local_tftp_root) / ioc_bin).rename(tftp_ioc_boot)
