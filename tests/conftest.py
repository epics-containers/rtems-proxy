"""
Shared fixtures for the rtems-proxy test suite.

The hybrid end-to-end tests (test_hybrid.py) drive the full
XML -> ioc.yaml -> st.cmd/ioc.subst -> /ioc_nfs pipeline. They depend on the
two ibek-support submodules checked out at the repo root; the DLS modules used
by the sample vacuum IOCs live in the internal-GitLab `ibek-support-dls`
submodule, so tests are skipped when it is not available (e.g. public CI).
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SAMPLES = REPO_ROOT / "tests" / "samples"
IBEK_SUPPORT = REPO_ROOT / "ibek-support"
IBEK_SUPPORT_DLS = REPO_ROOT / "ibek-support-dls"

# The sample vacuum IOCs need DLS-specific support modules (dlsPLC, DLS8515,
# vacuumSpace, ...) which live in the internal-GitLab ibek-support-dls
# submodule. Without it the schema is incomplete and generate2 would fail, so
# skip rather than report a spurious failure (mirrors builder2ibek's approach).
HAS_DLS_SUPPORT = any(IBEK_SUPPORT_DLS.glob("*/*.ibek.support.yaml"))

# builder2ibek is in the (non-default) `ci` dependency group, installed only
# where these tests run -- a DLS-internal runner / devcontainer. It is absent
# in the default `tests` env and on public CI (where it could not be installed
# anyway -- see pyproject [dependency-groups] ci), so gate on it too.
HAS_BUILDER2IBEK = shutil.which("builder2ibek") is not None

requires_dls = pytest.mark.skipif(
    not HAS_DLS_SUPPORT,
    reason="ibek-support-dls submodule not checked out (internal GitLab)",
)

requires_builder2ibek = pytest.mark.skipif(
    not HAS_BUILDER2IBEK,
    reason="builder2ibek not installed (run with: uv run --group ci pytest)",
)


@pytest.fixture
def samples() -> Path:
    return SAMPLES


@pytest.fixture
def fake_msi_bin(tmp_path: Path) -> Path:
    """
    A directory containing a stub `msi` executable, to be prepended to PATH.

    The real `msi` would expand ioc.subst against support-module db templates
    that only exist under /dls_sw (not in ibek-support). These tests validate
    the rtems-proxy hybrid orchestration and the ibek-generated st.cmd/ioc.subst
    -- not msi's db expansion -- so the stub just writes a placeholder to the
    -o<file> target and ignores everything else.
    """
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    msi = bindir / "msi"
    msi.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "out = next((a[2:] for a in sys.argv[1:] if a.startswith('-o')), None)\n"
        "if out:\n"
        "    open(out, 'w').write('# stub output from fake msi (hybrid e2e test)\\n')\n"
    )
    msi.chmod(msi.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


@pytest.fixture
def build_tree(tmp_path: Path) -> Path:
    """
    A stub IOC_ORIGINAL_LOCATION mimicking a generic-IOC build tree, containing
    just the parts the hybrid pipeline reads:

      ibek-support/, ibek-support-dls/   support YAMLs + autosave .req files
                                         (symlinked to the repo submodules)
      data/msi.vars                      sourced before msi (stubbed empty)
      data/<ioc>.proto                   StreamDevice protocol file (stub)
      dbd/ioc.dbd                        database definition (stub)
      bin/RTEMS-beatnik/ioc.boot         the boot binary (stub -- no cross
                                         compiler in CI)
    """
    orig = tmp_path / "build"
    (orig / "data").mkdir(parents=True)
    (orig / "dbd").mkdir()
    (orig / "bin" / "RTEMS-beatnik").mkdir(parents=True)

    (orig / "ibek-support").symlink_to(IBEK_SUPPORT)
    (orig / "ibek-support-dls").symlink_to(IBEK_SUPPORT_DLS)

    (orig / "data" / "msi.vars").write_text('export MSI_INCLUDES=""\n')
    (orig / "data" / "stub.proto").write_text("terminator = CR LF;\n")
    (orig / "dbd" / "ioc.dbd").write_text("# stub dbd\n")
    (orig / "bin" / "RTEMS-beatnik" / "ioc.boot").write_text("STUB BOOT IMAGE\n")
    return orig


def run_builder2ibek(xml: Path, out_yaml: Path) -> None:
    """Convert builder XML to ioc.yaml using the installed builder2ibek.

    builder2ibek is a CI-only dependency (see pyproject [dependency-groups]).
    Pinning it means Renovate raises a PR -- and runs these tests -- whenever a
    new builder2ibek is released, catching incompatibilities with rtems-proxy.
    """
    out_yaml.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["builder2ibek", "xml2yaml", str(xml), "--yaml", str(out_yaml)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"builder2ibek failed for {xml.name}:\n{result.stderr}"
    )


@pytest.fixture
def restore_globals():
    """Restore the GLOBALS singleton from the ambient environment after a test."""
    from rtems_proxy.globals import reload_globals

    yield
    for key in ("EPICS_ROOT", "IOC_ORIGINAL_LOCATION"):
        os.environ.pop(key, None)
    reload_globals()
