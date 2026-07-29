# Troubleshoot hybrid mode

## Run each phase by hand

If a step of [the pipeline](../reference/hybrid-pipeline.md) fails, run the
phases individually:

```bash
# Set up environment (or use --instance to do this automatically)
export IOC_NAME=BL-VA-IOC-01
export IOC_ORIGINAL_LOCATION=/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01

# 1. Symlink ibek-support YAMLs
mkdir -p /epics/ibek-defs/
ln -srf $IOC_ORIGINAL_LOCATION/ibek-support*/*/*.ibek.support.yaml /epics/ibek-defs/

# 2. Generate st.cmd and ioc.subst from ioc.yaml
ibek runtime generate2 /epics/ioc/config --no-pvi

# 3. Expand substitution file with msi
source $IOC_ORIGINAL_LOCATION/data/msi.vars
eval "msi -o/epics/runtime/ioc.db ${MSI_INCLUDES} -I/epics/runtime -S/epics/runtime/ioc.subst"

# 4. Build the master autosave request files
mkdir -p /epics/autosave
ln -srf $IOC_ORIGINAL_LOCATION/ibek-support*/*/*.req /epics/autosave/
ibek runtime generate-autosave /epics/runtime/ioc.subst

# 5. Verify outputs
ls /epics/runtime/st.cmd /epics/runtime/ioc.subst /epics/runtime/ioc.db \
   /epics/runtime/autosave_positions.req /epics/runtime/autosave_settings.req
```

## `No such file or directory: /epics/ibek-defs` (or `/ioc_nfs`, `/ioc_tftp`)

The devcontainer is running an image built before those directories were added
to the `Dockerfile` in June 2026. See
[](./set-up-the-devcontainer.md#check-the-working-directories-exist).

## ``No `definitions` given and none found in /epics/ibek-defs``

From `ibek ioc generate-schema` run with no arguments. The `--ibek-defs`
default only *adds* whatever is already in `/epics/ibek-defs`; it does not
populate it. Pass the Generic IOC's support YAMLs explicitly — see
[](./convert-builder-xml.md#generate-the-validation-schema).

## Schema validation errors from `ibek runtime generate2`

The `ioc.yaml` has fields that don't match the ibek support YAMLs. Common
causes:

- **Stale `ioc.yaml`** — re-run `builder2ibek` with the latest version.
- **Zero-indexed vs one-indexed fields** — older `builder2ibek` versions
  generated `ionp0`, `gauge0` where the support YAMLs expect `ionp1`, `gauge1`.
- **Unconverted entity types** — e.g. `vacuumValve.vacuumValveReadExtra` is not
  converted by `builder2ibek`. Comment these out of `ioc.yaml`.

## `msi: Can't open file`

The `.subst` file references DB template files via macros like
`$(DLSPLC)/db/...`. If `msi.vars` doesn't define a macro, or the module version
in `configure/RELEASE` doesn't contain the expected template, `msi` fails.

- Check the Generic IOC's `configure/RELEASE` includes all required support
  modules.
- Rebuild the Generic IOC (`make` in its top directory) to regenerate
  `data/msi.vars` after any RELEASE changes.
- Bare template filenames (without a `$(MODULE)/db/` prefix) in the `.subst`
  file indicate a bug in the ibek support YAML — the template path should use
  the module macro.

## `macro X is undefined`

`msi.vars` must be **sourced**, not just `MSI_INCLUDES`, because the `.subst`
file uses macros like `$(IOCSTATS)` in `file` directives and not only in `-I`
include paths. rtems-proxy handles this automatically; if running manually,
`source $IOC_ORIGINAL_LOCATION/data/msi.vars` before invoking `msi`.
