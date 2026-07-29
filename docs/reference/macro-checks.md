# Support module macro checks

ibek support YAMLs reference database templates by macro:

```yaml
- file: $(DIGITELSPC)/db/digitelSpc.template
```

The macro name is the module directory name uppercased — `digitelSpc` becomes
`DIGITELSPC`, `Hy8401ip-asyn` becomes `HY8401IP_ASYN`. The legacy IOC's
`configure/RELEASE` sometimes uses a historical short name instead, and
`data/msi.vars` is generated from RELEASE at build time. Where the two disagree,
msi cannot expand the path:

```
macLib: macro DIGITELSPC is undefined (expanding string $(DIGITELSPC)/db/digitelSpc.template)
```

which the pipeline only reports as `msi expansion failed`. Two checks catch this.

## Why two checks

A mismatch only *fails* if the affected entity type is actually instantiated.
`Hy8401ip` defines two entity types, and only `auto_Hy8401ip` has a database
referencing `$(HY8401IP)`; an IOC using just `Hy8401ip.Hy8401` never expands the
macro. Failing the run on every mismatch would block IOCs that work.

So the fatal check runs against the *generated* `ioc.subst` — every macro there
will genuinely be expanded — and the whole-YAML scan is advisory.

| | Fatal check (step 6) | Advisory scan (step 4) |
| --- | --- | --- |
| Input | generated `ioc.subst` | all linked support YAMLs |
| Reports | macros msi is about to fail on | modules defined under another name |
| On failure | stops the run | prints a warning |
| False positives | none | none, but findings may be latent |

Neither reports a module that is absent from `msi.vars` altogether — that just
means this IOC does not use it. Of the 139 YAMLs in the generic vacuum IOC, 109
are in that category.

Macros are only checked in `$(MACRO)/db/` paths. A bare `file "x.template"`
resolves through msi's `-I` include path and depends on no macro at all, so it
is skipped — and is the pattern that avoids this problem entirely.

## The `check` command

Run the advisory scan and a `configure/RELEASE` naming audit without the
pipeline:

```bash
rtems-proxy check --instance /workspaces/i15-services/services/bl15i-va-ioc-01
```

```
1 macro mismatch(es):

macro HY8401IP is not defined in /dls_sw/work/.../data/msi.vars
  used by: .../ibek-support-dls/Hy8401ip/Hy8401ip.ibek.support.yaml
  the module is defined as: HY8401=/dls_sw/prod/R7.0.7/support/Hy8401ip/3-21-RTEMS
  fix: name it HY8401IP in configure/RELEASE and rebuild the IOC, or use
       $(HY8401) in the support YAML

2 RELEASE macro(s) do not follow the module-name-uppercased convention:

  HY8401             -> Hy8401ip               expected HY8401IP
  AUTOSAVED          -> autosave               expected AUTOSAVE
```

Exit status is non-zero when there are mismatches. Convention violations are
reported but do not affect the exit status: they break nothing until a support
YAML references the expected name.

Pass `--no-convention` to skip the RELEASE audit.

`--instance` is not required — it is one of two ways to point the command at the
generic IOC build tree. The other is `IOC_ORIGINAL_LOCATION`, which the
Helm-rendered environment sets in a cluster, where there is no instance folder to
pass. Give it neither and the command says so rather than falling back to the
in-container `/epics/ioc` layout, which has no `msi.vars`.

## Fixing a mismatch

Either side can move, but they are not equivalent:

- **Rename in `configure/RELEASE`** to match the convention. Fixes one IOC, and
  every new IOC needs the same edit. **`msi.vars` is generated from RELEASE at
  build time, so the IOC must be rebuilt before the change takes effect** — the
  check detects this case and says so rather than repeating the mismatch.
- **Change the support YAML** to use the name RELEASE already defines. Fixes
  every IOC at once, but `ibek-support-dls` is shared, so it affects other
  facilities' beamlines too.
