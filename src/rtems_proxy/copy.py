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
    nfs_root = Path("/iocs") / GLOBALS.IOC_NAME

    # where to copy the Generic IOC folder to. This will contain the IOC binary
    # and the files
    dest_ioc = local_root / "ioc"
    # where to copy the generated runtime assets to. This will contain
    # st.cmd and ioc.db
    dest_runtime = local_root / "runtime"

    # TODO - perhaps do protocol files in this fashion for linux IOCs too,
    # in which case this needs to go somewhere generic
    protocol_folder = GLOBALS.RUNTIME / "protocol"
    protocol_folder.mkdir(parents=True, exist_ok=True)
    protocol_files = GLOBALS.SUPPORT.glob("**/*.proto*")
    for proto_file in protocol_files:
        dest = protocol_folder / proto_file.name
        shutil.copy(proto_file, dest)

    # copy all the files needed for runtime into the PVC that is being shared
    # over nfs/tftp by the nfsv2-tftp service
    for folder in ["bin", "dbd"]:
        shutil.copytree(
            GLOBALS.IOC.readlink() / folder, dest_ioc / folder, dirs_exist_ok=True
        )
    shutil.copytree(GLOBALS.RUNTIME, dest_runtime, dirs_exist_ok=True)

    # because we moved the ioc files we need to fix up startup script paths
    startup = dest_runtime / "st.cmd"
    cmd_txt = startup.read_text()
    cmd_txt = re.sub("/epics/", f"{str(nfs_root)}/", cmd_txt)
    # also fix up the protocol path to point to protocol_folder
    cmd_txt = (
        cmd_txt
        + f'\nepicsEnvSet("STREAM_PROTOCOL_PATH", "{str(nfs_root / "runtime" / "protocol")}")\n'
    )
    startup.write_text(cmd_txt)
