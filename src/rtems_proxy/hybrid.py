"""
Hybrid mode: generate IOC runtime assets from ibek + msi and place them
for an RTEMS crate to boot from NFS/TFTP.
"""

import os
import subprocess
from pathlib import Path

import typer

from .globals import GLOBALS
from .telnet import report


def hybrid_prepare(instance_path: Path | None = None):
    """
    Run the full hybrid IOC preparation sequence: generate runtime files
    from ibek + msi, then place all assets on NFS and TFTP for the
    RTEMS crate to boot.

    If instance_path is given, symlink its config/ into IOC_CONFIG_PATH
    so that ibek can find the ioc.yaml.
    """
    GLOBALS.RUNTIME.mkdir(parents=True, exist_ok=True)
    GLOBALS.RTEMS_NFS_ROOT_PATH.mkdir(parents=True, exist_ok=True)
    GLOBALS.RTEMS_TFTP_ROOT_PATH.mkdir(parents=True, exist_ok=True)

    if instance_path:
        _link_instance_config(instance_path)

    _link_ibek_support_yamls()
    _run_ibek_generate()
    _run_msi()
    _copy_to_nfs()
    _copy_binary_to_tftp()


def _link_instance_config(instance_path: Path):
    """
    Symlink the instance config directory into IOC_CONFIG_PATH so ibek
    can discover ioc.yaml — replaces the manual 'ibek dev instance' step.
    """
    config_src = instance_path / "config"
    if not config_src.exists():
        typer.echo(f"No config directory found at {config_src}")
        raise typer.Exit(1)

    config_dst = GLOBALS.IOC_CONFIG_PATH
    if config_dst.is_symlink():
        config_dst.unlink()
    elif config_dst.exists():
        import shutil

        shutil.rmtree(config_dst)

    config_dst.parent.mkdir(parents=True, exist_ok=True)
    config_dst.symlink_to(config_src)
    report(f"Linked instance config {config_src} -> {config_dst}")


def _link_ibek_support_yamls():
    """
    Symlink ibek-support YAML definitions from the generic IOC into
    the ibek-defs directory so ibek can discover them.
    """
    ibek_defs = GLOBALS.IBEK_DEFS_PATH
    ibek_defs.mkdir(parents=True, exist_ok=True)

    for existing in ibek_defs.glob("*.ibek.support.yaml"):
        if existing.is_symlink():
            existing.unlink()

    ioc_root = GLOBALS.IOC_ORIGINAL_LOCATION
    yaml_files = list(ioc_root.glob("ibek-support*/*/*.ibek.support.yaml"))

    if not yaml_files:
        typer.echo(f"No .ibek.support.yaml files found under {ioc_root}/ibek-support*/")
        raise typer.Exit(1)

    for yaml_file in yaml_files:
        link = ibek_defs / yaml_file.name
        if link.exists():
            link.unlink()
        link.symlink_to(yaml_file)

    report(f"Linked {len(yaml_files)} ibek support YAMLs into {ibek_defs}")


def _run_ibek_generate():
    """
    Run ibek runtime generate2 to produce st.cmd and ioc.subst
    from the instance ioc.yaml.
    """
    config_dir = GLOBALS.IOC_CONFIG_PATH
    if not config_dir.exists():
        typer.echo(f"IOC config directory {config_dir} does not exist")
        raise typer.Exit(1)

    # ibek's st.cmd template renders 'dbLoadRecords {RUNTIME_DIR}/ioc.db' from
    # the RUNTIME_DIR env var (no default -- empty yields a bad '/ioc.db' path).
    # Point it at the runtime folder the crate mounts at /epics/runtime.
    env = {**os.environ, "RUNTIME_DIR": str(GLOBALS.RUNTIME)}

    cmd = ["ibek", "runtime", "generate2", str(config_dir), "--no-pvi"]
    report(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False, env=env)
    if result.returncode != 0:
        typer.echo("ibek runtime generate2 failed")
        raise typer.Exit(1)

    for expected in ["st.cmd", "ioc.subst"]:
        if not (GLOBALS.RUNTIME / expected).exists():
            typer.echo(f"ibek did not produce {GLOBALS.RUNTIME / expected}")
            raise typer.Exit(1)

    report("ibek generate2 completed")


def _run_msi():
    """
    Expand ioc.subst into ioc.db using msi with include paths from msi.vars.

    The subst file references macros like $(IOCSTATS) in file paths, so we
    source the full msi.vars to make all macro definitions available to msi.
    """
    msi_vars = GLOBALS.IOC_ORIGINAL_LOCATION / "data" / "msi.vars"
    runtime = str(GLOBALS.RUNTIME)

    cmd = (
        f'source "{msi_vars}" && '
        f"msi -o{runtime}/ioc.db $MSI_INCLUDES -I{runtime} -S{runtime}/ioc.subst"
    )
    report("Running msi")
    result = subprocess.run(["bash", "-c", cmd], check=False)
    if result.returncode != 0:
        typer.echo("msi expansion failed")
        raise typer.Exit(1)

    if not (GLOBALS.RUNTIME / "ioc.db").exists():
        typer.echo(f"msi did not produce {GLOBALS.RUNTIME / 'ioc.db'}")
        raise typer.Exit(1)

    report("msi expansion completed")


def _copy_to_nfs():
    """
    Place runtime files into the NFS root under two subfolders that match the
    paths the generated st.cmd expects once the crate has NFS-mounted the root
    at /epics:

      runtime/  st.cmd, ioc.db, the protocol/ folder and autosave *.req files
                (st.cmd: epics-script=/epics/runtime/st.cmd,
                 STREAM_PROTOCOL_PATH=/epics/runtime/protocol/,
                 set_requestfile_path("/epics", "runtime"))
      ioc/      the dbd/ folder
                (st.cmd: cd "/epics/ioc"; dbLoadDatabase dbd/ioc.dbd)
    """
    nfs = GLOBALS.RTEMS_NFS_ROOT_PATH
    runtime = GLOBALS.RUNTIME
    ioc_root = GLOBALS.IOC_ORIGINAL_LOCATION

    nfs_runtime = Path(nfs) / "runtime"
    nfs_ioc = Path(nfs) / "ioc"
    nfs_runtime.mkdir(parents=True, exist_ok=True)
    nfs_ioc.mkdir(parents=True, exist_ok=True)

    # runtime/: startup script and the expanded database
    subprocess.run(
        ["rsync", f"{runtime}/st.cmd", f"{nfs_runtime}/"],
        check=True,
    )
    subprocess.run(
        ["rsync", f"{runtime}/ioc.db", f"{nfs_runtime}/"],
        check=True,
    )

    # runtime/protocol/: StreamDevice protocol files (data/*.proto*)
    protocol_dir = nfs_runtime / "protocol"
    protocol_dir.mkdir(parents=True, exist_ok=True)
    proto_files = list((ioc_root / "data").glob("*.proto*"))
    if proto_files:
        subprocess.run(
            ["rsync"] + [str(f) for f in proto_files] + [f"{protocol_dir}/"],
            check=True,
        )

    # runtime/: autosave request files -- st.cmd searches /epics/runtime for
    # them via set_requestfile_path("/epics", "runtime")
    req_files = list(Path(runtime).glob("*.req"))
    if req_files:
        subprocess.run(
            ["rsync"] + [str(f) for f in req_files] + [f"{nfs_runtime}/"],
            check=True,
        )

    # ioc/dbd/: database definition loaded by 'cd /epics/ioc; dbLoadDatabase'
    dbd_src = ioc_root / "dbd"
    if dbd_src.exists():
        subprocess.run(
            ["rsync", "-r", f"{dbd_src}/", f"{nfs_ioc}/dbd/"],
            check=True,
        )

    report(f"Placed runtime files in {nfs_runtime} and {nfs_ioc}")


def _copy_binary_to_tftp():
    """
    Copy the IOC .boot binary to TFTP with the standard name.
    """
    tftp = GLOBALS.RTEMS_TFTP_ROOT_PATH
    # source .boot is named after the build folder (IOC_BUILD_NAME), not the
    # deployment IOC_NAME -- these differ for legacy builds (e.g.
    # BL-VA-IOC-01.boot under .../bl-va-ioc-01 deployed as bl19i-va-ioc-01)
    ioc_bin_name = f"{GLOBALS.IOC_BUILD_NAME.upper()}.boot"
    ioc_bin_src = GLOBALS.IOC_ORIGINAL_LOCATION / "bin" / "RTEMS-beatnik" / ioc_bin_name

    if not ioc_bin_src.exists():
        typer.echo(f"IOC binary not found at {ioc_bin_src}")
        raise typer.Exit(1)

    subprocess.run(
        ["rsync", str(ioc_bin_src), f"{tftp}/"],
        check=True,
    )

    tftp_target = Path(tftp) / GLOBALS.RTEMS_BINARY_DEFAULT_NAME
    tftp_target.unlink(missing_ok=True)
    (Path(tftp) / ioc_bin_name).rename(tftp_target)

    report(f"Placed IOC binary at {tftp_target}")
