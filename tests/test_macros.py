"""
Unit tests for the support-module macro consistency checks.

These use fixture trees rather than the ibek-support submodules, so unlike the
hybrid end-to-end tests they run everywhere including public CI.

The cases mirror what was found in the real generic vacuum IOC:

  digitelSpc   YAML uses $(DIGITELSPC), RELEASE defines SPC       -- fired
  Hy8401ip     YAML uses $(HY8401IP),   RELEASE defines HY8401    -- latent,
               because only the auto_Hy8401ip entity (not instantiated) has a
               database referencing the macro
"""

from pathlib import Path

import pytest

from rtems_proxy.macros import (
    check_release_convention,
    check_subst_macros,
    check_support_yamls,
    parse_msi_vars,
    subst_macros,
)

SUPPORT = "/dls_sw/prod/R7.0.7/support"


@pytest.fixture
def ioc_root(tmp_path: Path) -> Path:
    """A stub generic-IOC build tree with two support YAMLs and an msi.vars."""
    root = tmp_path / "build"
    (root / "data").mkdir(parents=True)
    (root / "configure").mkdir()

    def support_yaml(module: str, macro: str) -> None:
        d = root / "ibek-support-dls" / module
        d.mkdir(parents=True)
        (d / f"{module}.ibek.support.yaml").write_text(
            f"module: {module}\n"
            "defs:\n"
            f"  - name: {module}\n"
            "    databases:\n"
            f"      - file: $({macro})/db/{module}.template\n"
        )

    # digitelMpc matches; digitelSpc does not (defined below as SPC)
    support_yaml("digitelMpc", "DIGITELMPC")
    support_yaml("digitelSpc", "DIGITELSPC")

    (root / "data" / "msi.vars").write_text(
        "#!/bin/bash\n"
        f"export DIGITELMPC={SUPPORT}/digitelMpc/7-0\n"
        f"export SPC={SUPPORT}/digitelSpc/2-0\n"
        f'export MSI_INCLUDES=" -I{SUPPORT}/digitelMpc/7-0/db'
        f' -I{SUPPORT}/digitelSpc/2-0/db"\n'
    )
    (root / "configure" / "RELEASE").write_text(
        "SUPPORT=/dls_sw/prod/R7.0.7/support\n"
        "DIGITELMPC=$(SUPPORT)/digitelMpc/7-0\n"
        "SPC=$(SUPPORT)/digitelSpc/2-0\n"
    )
    return root


def write_subst(tmp_path: Path, *lines: str) -> Path:
    subst = tmp_path / "ioc.subst"
    subst.write_text("\n".join(lines) + "\n")
    return subst


def test_parse_msi_vars_strips_quotes(ioc_root: Path):
    defined = parse_msi_vars(ioc_root / "data" / "msi.vars")
    assert defined["DIGITELMPC"] == f"{SUPPORT}/digitelMpc/7-0"
    assert defined["MSI_INCLUDES"].startswith(" -I")


def test_subst_macros_ignores_bare_filenames(tmp_path: Path):
    subst = write_subst(
        tmp_path,
        'file "$(DIGITELMPC)/db/digitelMpc.template" {',
        'file "generalTime.template" {',
    )
    # bare filenames resolve through msi's -I path and need no macro
    assert subst_macros(subst) == {"DIGITELMPC"}


def test_matching_macro_passes(ioc_root: Path, tmp_path: Path):
    subst = write_subst(tmp_path, 'file "$(DIGITELMPC)/db/digitelMpc.template" {')
    assert check_subst_macros(subst, ioc_root, ioc_root / "data" / "msi.vars") == []


def test_mismatch_fails_and_names_the_alias(ioc_root: Path, tmp_path: Path):
    subst = write_subst(tmp_path, 'file "$(DIGITELSPC)/db/digitelSpc.template" {')
    found = check_subst_macros(subst, ioc_root, ioc_root / "data" / "msi.vars")

    assert len(found) == 1
    mismatch = found[0]
    assert mismatch.macro == "DIGITELSPC"
    assert mismatch.module == "digitelSpc"
    assert mismatch.alias == "SPC"
    assert not mismatch.stale

    described = mismatch.describe(ioc_root / "data" / "msi.vars")
    assert "SPC=" in described
    # MSI_INCLUDES contains every module path, so it must never be offered as
    # the alias -- it would match any module and mislead the fix
    assert "MSI_INCLUDES" not in described


def test_unused_module_not_reported_by_hard_check(ioc_root: Path, tmp_path: Path):
    """A macro no subst line uses cannot fail msi, so must not block the run."""
    subst = write_subst(tmp_path, 'file "$(DIGITELMPC)/db/digitelMpc.template" {')
    assert check_subst_macros(subst, ioc_root, ioc_root / "data" / "msi.vars") == []


def test_advisory_reports_latent_mismatch(ioc_root: Path):
    """The same mismatch is still surfaced as advisory, with no subst involved."""
    found = check_support_yamls(ioc_root, ioc_root / "data" / "msi.vars")
    assert [m.macro for m in found] == ["DIGITELSPC"]


def test_advisory_ignores_module_absent_from_build(ioc_root: Path):
    """A module not in msi.vars at all is unused by this IOC, not a mismatch."""
    unused = ioc_root / "ibek-support-dls" / "zebra"
    unused.mkdir(parents=True)
    (unused / "zebra.ibek.support.yaml").write_text(
        "defs:\n  - name: zebra\n    databases:\n      - file: $(ZEBRA)/db/zebra.template\n"
    )
    found = check_support_yamls(ioc_root, ioc_root / "data" / "msi.vars")
    assert [m.macro for m in found] == ["DIGITELSPC"]


def test_stale_msi_vars_detected(ioc_root: Path, tmp_path: Path):
    """RELEASE fixed but not rebuilt: msi.vars still has the old name."""
    (ioc_root / "configure" / "RELEASE").write_text(
        "SUPPORT=/dls_sw/prod/R7.0.7/support\n"
        "DIGITELSPC=$(SUPPORT)/digitelSpc/2-0\n"  # fixed here...
    )
    # ...but msi.vars, generated at build time, still exports SPC
    subst = write_subst(tmp_path, 'file "$(DIGITELSPC)/db/digitelSpc.template" {')
    found = check_subst_macros(subst, ioc_root, ioc_root / "data" / "msi.vars")

    assert len(found) == 1
    assert found[0].stale
    assert "rebuild the IOC" in found[0].describe(ioc_root / "data" / "msi.vars")


def test_release_convention_flags_outliers(ioc_root: Path):
    (ioc_root / "configure" / "RELEASE").write_text(
        "SUPPORT=/dls_sw/prod/R7.0.7/support\n"
        "EPICS_BASE=/dls_sw/epics/R7.0.7/base\n"  # not a support module
        "DIGITELMPC=$(SUPPORT)/digitelMpc/7-0\n"  # conforms
        "HY8401=$(SUPPORT)/Hy8401ip/3-21-RTEMS\n"  # outlier
        "TIMING=$(SUPPORT)/mrfTiming/2-4-1dls11\n"  # outlier
        "HY8401IP_ASYN=$(SUPPORT)/Hy8401ip-asyn/1-0\n"  # hyphen -> underscore
    )
    violations = check_release_convention(ioc_root / "configure" / "RELEASE")
    assert violations == [
        ("HY8401", "Hy8401ip", "HY8401IP"),
        ("TIMING", "mrfTiming", "MRFTIMING"),
    ]


def test_check_command_without_instance_explains_itself(monkeypatch):
    """`rtems-proxy check` with no IOC to check must not fall back silently.

    IOC_ORIGINAL_LOCATION defaults to /epics/ioc (the in-container ibek build
    layout), so a bare `check` would otherwise report a confusing missing
    msi.vars for a tree the user never asked about.
    """
    from typer.testing import CliRunner

    from rtems_proxy.__main__ import cli

    monkeypatch.delenv("IOC_ORIGINAL_LOCATION", raising=False)
    result = CliRunner().invoke(cli, ["check"])

    assert result.exit_code == 2
    assert "--instance" in result.output
    assert "IOC_ORIGINAL_LOCATION" in result.output
