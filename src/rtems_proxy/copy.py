"""
functions for moving IOC assets into position for a remote IOC to access
"""

import shutil

from .globals import GLOBALS


def copy_rtems():
    """
    Copy RTEMS IOC binary and startup assets to a location where the RTEMS IOC
    can access them

    IMPORTANT: local_root and nfs_root are different perspectives on the same
               folder.
    local_root: where the IOC files will be placed from the
                perspective of this IOC proxy service. This IOC proxy will
                populate the folder for use by the RTEMS crate.
    nfs_root:   where the IOC files will be found from the perspective of a
                a client to the nfsv2-tftp service. i.e. where the RTEMS crate
                will look for them using NFS.
    """
    local_root = GLOBALS.RTEMS_TFTP_PATH

    # where to copy the Generic IOC folder to. This will contain the IOC binary
    # and the files
    dest_ioc = local_root / "ioc"
    # where to copy the generated runtime assets to. This will contain
    # st.cmd and ioc.db
    dest_runtime = local_root / "runtime"

    # make sure all files are writable - by default some products are read-only
    for folder in [dest_ioc, dest_runtime]:
        for file in folder.glob("**/*"):
            file.chmod(0o666)

    # copy all the files needed for runtime into the PVC that is being shared
    # over nfs/tftp by the nfsv2-tftp service
    for folder in ["bin", "dbd"]:
        shutil.copytree(
            GLOBALS.IOC.readlink() / folder, dest_ioc / folder, dirs_exist_ok=True
        )
    shutil.copytree(GLOBALS.RUNTIME, dest_runtime, dirs_exist_ok=True)
