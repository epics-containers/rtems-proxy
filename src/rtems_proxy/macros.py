"""
Macro consistency checks between ibek-support YAMLs and the generic IOC build.

ibek support YAMLs reference support-module template paths as
``$(MACRO)/db/x.template``, where MACRO is the module directory name uppercased.
The legacy IOC's ``configure/RELEASE`` (and the ``data/msi.vars`` generated from
it) sometimes uses a historical short name instead -- ``SPC`` for ``digitelSpc``,
``HY8401`` for ``Hy8401ip``. Where the two disagree, msi fails with

    macLib: macro DIGITELSPC is undefined (expanding string $(DIGITELSPC)/db/...)

which surfaces only as ``msi expansion failed``. These checks catch it first and
name the fix.
"""

import re
from dataclasses import dataclass
from pathlib import Path

# msi.vars defines MSI_INCLUDES as every module's db directory concatenated, so
# it matches every module path and is useless (actively misleading) when looking
# for the macro a module is actually defined under.
_NOT_A_MODULE = {"MSI_INCLUDES"}

_EXPORT_RE = re.compile(r"^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_RELEASE_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\S+)")
_SUBST_FILE_RE = re.compile(r'^file\s+"\$\(([A-Z][A-Z0-9_]*)\)')
_YAML_MACRO_RE = re.compile(r"\$\(([A-Z][A-Z0-9_]*)\)/db/")
_MODULE_RE = re.compile(r"\$\((?:SUPPORT|WORK)\)/([^/\s]+)")


@dataclass
class Mismatch:
    """A macro a support YAML needs that the build does not define."""

    macro: str
    """The macro name the support YAML uses, e.g. DIGITELSPC."""
    module: str
    """The support module directory name, e.g. digitelSpc."""
    yaml: Path | None
    """The support YAML that references it, when known."""
    alias: str | None
    """The macro the module IS defined under, e.g. SPC, when one exists."""
    alias_value: str | None
    """The path that alias points at."""
    stale: bool = False
    """configure/RELEASE already names it correctly -- msi.vars is out of date."""

    def describe(self, msi_vars: Path) -> str:
        lines = [f"macro {self.macro} is not defined in {msi_vars}"]
        if self.yaml:
            lines.append(f"  used by: {self.yaml}")
        if self.stale:
            lines.append(
                f"  configure/RELEASE already defines {self.macro}, but msi.vars is"
                " generated from RELEASE at build time and has not been"
                " regenerated -- rebuild the IOC to pick the change up"
            )
        elif self.alias:
            lines.append(f"  the module is defined as: {self.alias}={self.alias_value}")
            lines.append(
                f"  fix: name it {self.macro} in configure/RELEASE and rebuild the"
                f" IOC, or use $({self.alias}) in the support YAML"
            )
        else:
            lines.append(
                f"  no definition for module {self.module} was found -- is it"
                " missing from configure/RELEASE?"
            )
        return "\n".join(lines)


def parse_msi_vars(msi_vars: Path) -> dict[str, str]:
    """Extract ``export NAME=value`` pairs from a generated msi.vars."""
    defined: dict[str, str] = {}
    for line in msi_vars.read_text().splitlines():
        match = _EXPORT_RE.match(line.strip())
        if match:
            defined[match.group(1)] = match.group(2).strip().strip('"')
    return defined


def parse_release(release: Path) -> dict[str, str]:
    """Extract ``NAME=$(SUPPORT)/module/version`` pairs from a configure/RELEASE."""
    return {
        m.group(1): m.group(2)
        for m in (_RELEASE_RE.match(line) for line in release.read_text().splitlines())
        if m
    }


def support_yaml_macros(ioc_root: Path) -> dict[str, tuple[str, Path]]:
    """
    Map each macro used in a support YAML db path to (module, yaml).

    Uses the same glob as the hybrid pipeline's YAML linking step, so the
    checked set is exactly the set that will be used to generate.
    """
    found: dict[str, tuple[str, Path]] = {}
    for yaml in sorted(ioc_root.glob("ibek-support*/*/*.ibek.support.yaml")):
        for macro in _YAML_MACRO_RE.findall(yaml.read_text()):
            found.setdefault(macro, (yaml.parent.name, yaml))
    return found


def subst_macros(subst: Path) -> set[str]:
    """
    Collect macros used in ``file "$(MACRO)/..."`` lines of a substitution file.

    Bare filenames are ignored: msi resolves those through its -I include path,
    so they do not depend on a macro name at all.
    """
    return {
        m.group(1)
        for m in (_SUBST_FILE_RE.match(line) for line in subst.read_text().splitlines())
        if m
    }


def _find_alias(module: str, defined: dict[str, str]) -> tuple[str | None, str | None]:
    """Find the macro a module is defined under, if not the expected name."""
    pattern = re.compile(rf"/{re.escape(module)}(/|$)")
    for name, value in defined.items():
        if name not in _NOT_A_MODULE and pattern.search(value):
            return name, value
    return None, None


def _mismatches(
    macros: dict[str, tuple[str, Path | None]],
    wanted: set[str] | None,
    defined: dict[str, str],
    in_release: set[str],
) -> list[Mismatch]:
    """Build Mismatch records for undefined macros, skipping unused modules."""
    result = []
    for macro, (module, yaml) in sorted(macros.items()):
        if macro in defined:
            continue
        if wanted is not None and macro not in wanted:
            continue
        alias, alias_value = _find_alias(module, defined)
        if wanted is None and alias is None:
            # Advisory mode: a module absent from msi.vars entirely is simply
            # not used by this IOC. Only a module present under a DIFFERENT
            # name is a genuine naming mismatch.
            continue
        result.append(
            Mismatch(macro, module, yaml, alias, alias_value, macro in in_release)
        )
    return result


def _release_macros(ioc_root: Path) -> set[str]:
    """Macro names defined in the IOC's configure/RELEASE, if it is readable."""
    release = ioc_root / "configure" / "RELEASE"
    try:
        return set(parse_release(release))
    except OSError:
        return set()


def check_subst_macros(subst: Path, ioc_root: Path, msi_vars: Path) -> list[Mismatch]:
    """
    Hard check: every macro the generated subst file will expand must be defined.

    Runs against the generated ioc.subst, so every macro reported here is one
    msi is about to fail on -- no false positives.
    """
    defined = parse_msi_vars(msi_vars)
    wanted = subst_macros(subst)
    macros: dict[str, tuple[str, Path | None]] = dict(support_yaml_macros(ioc_root))
    # a macro used in the subst but traceable to no YAML still gets reported
    for macro in wanted:
        macros.setdefault(macro, (macro.lower(), None))
    return _mismatches(macros, wanted, defined, _release_macros(ioc_root))


def check_support_yamls(ioc_root: Path, msi_vars: Path) -> list[Mismatch]:
    """
    Advisory check: any support YAML whose macro is undefined but whose module
    IS defined under another name.

    Catches latent mismatches -- a module whose entity types are not yet
    instantiated by this IOC, so nothing fails today. Never fatal.
    """
    defined = parse_msi_vars(msi_vars)
    macros: dict[str, tuple[str, Path | None]] = dict(support_yaml_macros(ioc_root))
    return _mismatches(macros, None, defined, _release_macros(ioc_root))


def check_release_convention(release: Path) -> list[tuple[str, str, str]]:
    """
    Report RELEASE macros that are not their module directory name uppercased.

    Returns (macro, module, expected) triples. This is the convention that lets
    ibek-support YAMLs be portable across IOCs; an outlier is a latent trap even
    when nothing references it yet.
    """
    violations = []
    for macro, value in parse_release(release).items():
        module_match = _MODULE_RE.match(value)
        if not module_match:
            continue  # not a support module reference (EPICS_BASE, WORK, ...)
        module = module_match.group(1)
        expected = module.upper().replace("-", "_")
        if macro != expected:
            violations.append((macro, module, expected))
    return violations
