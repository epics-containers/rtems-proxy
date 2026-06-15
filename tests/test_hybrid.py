"""
End-to-end tests for hybrid mode.

Mirrors the builder2ibek "generate and compare" approach: for each sample
builder XML, run the whole hybrid pipeline and compare against committed
baselines.

    builder XML
      --(builder2ibek xml2yaml)-->        ioc.yaml
      --(ibek runtime generate2)-->       st.cmd + ioc.subst   <-- compared
      --(msi, STUBBED)-->                 ioc.db
      --(ibek runtime generate-autosave)--> autosave_*.req
      --(rsync)-->                        /ioc_nfs, /ioc_tftp   <-- placement

The genuinely-validated artifacts are st.cmd and ioc.subst (produced by ibek
from the pinned ibek-support* submodules). The msi -> ioc.db expansion needs
support-module db templates that only exist under /dls_sw, and there is no
cross-compiled .boot binary in CI, so msi is stubbed (conftest.fake_msi_bin)
and the dbd/proto/binary inputs are stubbed (conftest.build_tree). For those we
assert only that the pipeline places them where the crate's st.cmd expects.
"""

import os
from pathlib import Path

import pytest

from rtems_proxy.globals import GLOBALS, reload_globals
from tests.conftest import SAMPLES, requires_dls, run_builder2ibek

SAMPLE_XMLS = sorted(SAMPLES.glob("*.xml"))
SAMPLE_IDS = [x.stem for x in SAMPLE_XMLS]


@requires_dls
@pytest.mark.parametrize("sample_xml", SAMPLE_XMLS, ids=SAMPLE_IDS)
def test_hybrid_generate(
    sample_xml: Path,
    tmp_path: Path,
    build_tree: Path,
    fake_msi_bin: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_globals,
):
    stem = sample_xml.stem.lower()
    expected_stcmd = SAMPLES / f"{stem}.st.cmd"
    expected_subst = SAMPLES / f"{stem}.ioc.subst"
    assert expected_stcmd.exists(), (
        f"no baseline for {stem} -- run tests/samples/make_samples.sh"
    )

    epics_root = tmp_path / "epics"
    nfs_root = tmp_path / "ioc_nfs"
    tftp_root = tmp_path / "ioc_tftp"

    # Point GLOBALS at the temp build/runtime tree, and put the stub msi first
    # on PATH so the (real) ibek subprocesses resolve it ahead of the venv's.
    monkeypatch.setenv("EPICS_ROOT", str(epics_root))
    monkeypatch.setenv("IOC_ORIGINAL_LOCATION", str(build_tree))
    monkeypatch.setenv("PATH", f"{fake_msi_bin}{os.pathsep}{os.environ['PATH']}")
    reload_globals()
    # RTEMS_{NFS,TFTP}_ROOT_PATH are hard-coded to /ioc_{nfs,tftp}; redirect them.
    monkeypatch.setattr(GLOBALS, "RTEMS_NFS_ROOT_PATH", nfs_root)
    monkeypatch.setattr(GLOBALS, "RTEMS_TFTP_ROOT_PATH", tftp_root)

    # stage 1: builder XML -> ioc.yaml, placed where ibek will look for it
    run_builder2ibek(sample_xml, GLOBALS.IOC_CONFIG_PATH / "ioc.yaml")

    # stages 2-8: the full hybrid pipeline (msi stubbed)
    from rtems_proxy import hybrid

    hybrid.hybrid_prepare(instance_path=None)

    # --- the validated artifacts: st.cmd + ioc.subst content ---
    # ibek bakes the absolute RUNTIME_DIR into st.cmd; baselines canonicalise
    # the temp EPICS_ROOT to /epics (what the crate mounts), so do the same here.
    runtime = GLOBALS.RUNTIME

    def norm(text: str) -> str:
        return text.replace(str(epics_root), "/epics").rstrip()

    assert norm((runtime / "st.cmd").read_text()) == norm(expected_stcmd.read_text()), (
        f"st.cmd mismatch for {stem} -- if ibek-support* changed intentionally, "
        f"re-run tests/samples/make_samples.sh and review the diff"
    )
    assert norm((runtime / "ioc.subst").read_text()) == norm(
        expected_subst.read_text()
    ), f"ioc.subst mismatch for {stem} -- re-run tests/samples/make_samples.sh"

    # --- placement: the crate boots by NFS-mounting this tree at /epics ---
    # runtime/ : st.cmd, the (stub) expanded db, protocol files, autosave reqs
    nfs_runtime = nfs_root / "runtime"
    assert (nfs_runtime / "st.cmd").read_text() == (runtime / "st.cmd").read_text()
    assert (nfs_runtime / "ioc.db").exists()
    assert (nfs_runtime / "protocol" / "stub.proto").exists()
    assert sorted(p.name for p in nfs_runtime.glob("*.req")) == [
        "autosave_positions.req",
        "autosave_settings.req",
    ]
    # ioc/dbd/ : database definition loaded by 'cd /epics/ioc; dbLoadDatabase'
    assert (nfs_root / "ioc" / "dbd" / "ioc.dbd").exists()
    # the boot binary lands in TFTP under the standard name
    assert (tftp_root / GLOBALS.RTEMS_BINARY_DEFAULT_NAME).exists()
