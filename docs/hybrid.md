# RTEMS Hybrid IOCs

This page describes the hybrid approach: using a pre-built Generic IOC binary
from the DLS build server combined with ibek-generated runtime configuration,
all managed by Kubernetes via rtems-proxy.

This is the quickest way to convert existing VxWorks XmlBuilder IOCs to RTEMS5.

## Overview

A hybrid IOC combines three pieces:

1. **A Generic RTEMS5 IOC binary** — shared across all beamlines for a given
   class of IOC (e.g. beamline vacuum). Built and released via the DLS build
   server to `/dls_sw/prod` or may be run out of `/dls_sw/work`.
2. **An `ioc.yaml` instance definition** — auto-converted from the existing
   VxWorks builder XML using `builder2ibek`. Lives in the beamline services
   repository (e.g. `i19-services/services/bl19i-va-ioc-01/config/ioc.yaml`).
3. **rtems-proxy with `--hybrid` mode** — at runtime, uses ibek + msi to
   generate `st.cmd` and `ioc.db` from the instance definition, then places
   all assets on NFS/TFTP for the RTEMS crate to boot.

## Prerequisites

### The Generic IOC

The Generic IOC is maintained at
<https://gitlab.diamond.ac.uk/controls/ioc/BL> as a native EPICS 7, RTEMS5
IOC. See [confluence](https://confluence.diamond.ac.uk/x/_w6WFQ) for build
details.

It has a few special additions beyond a standard EPICS IOC:

- **ibek-support submodules** (`ibek-support/` and `ibek-support-dls/`) so
  that ibek support YAML versions are tracked with the IOC binary version.
- **A modified `src/Makefile`** that collects all stream device protocol files
  into the `data/` folder, for easy protocol file path management.
- **A Makefile rule to generate `data/msi.vars`** from `configure/RELEASE`.

#### `data/msi.vars`

The top-level `Makefile` auto-generates `data/msi.vars` whenever
`configure/RELEASE` changes. This file exports every module path from RELEASE
as a shell variable, plus a composite `MSI_INCLUDES` variable listing all
`-I<module>/db` flags:

```makefile
all: data/msi.vars

data/msi.vars: $(TOP)/configure/RELEASE
	@echo "#!/bin/bash" > $@
	@echo "# Auto-generated from configure/RELEASE" >> $@
	@$(foreach var,$(RELEASE_VARS),echo "export $(var)=$($(var))" >> $@;)
	@echo "export MSI_INCLUDES=\"$(SYS_MSI_INCLUDES)\"" >> $@
```

At hybrid runtime, rtems-proxy sources this file before running `msi`, which
makes all macros like `$(IOCSTATS)`, `$(DLSPLC)` etc. available for resolving
paths in the `.subst` file.

#### Protocol files

The Makefile also copies all `.proto*` files from support modules into `data/`:

```makefile
all_protos = $(foreach path,$(subst :, ,$(SYS_EDM_PATHS)),$(wildcard $(path)/*.proto*))
DATA += $(all_protos)
```

These are then placed on the NFS share by rtems-proxy at runtime.

## Generating `ioc.yaml` with builder2ibek

Use `builder2ibek` to convert the existing VxWorks builder XML into an ibek
instance definition:

```bash
uvx builder2ibek xml2yaml \
    --yaml <services-repo>/services/<ioc-name>/config/ioc.yaml \
    <path-to-builder-xml>
```

For example, for bl19i-va-ioc-01:

```bash
uvx builder2ibek xml2yaml \
    --yaml /workspaces/i19-services/services/bl19i-va-ioc-01/config/ioc.yaml \
    /dls_sw/prod/R3.14.12.7/support/BL19I-BUILDER/2024-Run1-2/etc/makeIocs/BL19I-VA-IOC-01.xml
```

### Validating the generated ioc.yaml

You can generate a JSON schema from the ibek support YAMLs and use it to
validate the `ioc.yaml` before attempting a full hybrid run:

```bash
ibek ioc generate-schema --output /epics/ibek-defs/ioc.schema.json
```

Add this to the top of `ioc.yaml` to enable editor validation:

```yaml
# yaml-language-server: $schema=/epics/ibek-defs/ioc.schema.json
```

### Known builder2ibek issues

- `builder2ibek` converts `vacuumValve` entities to `dlsPLC`, but misses
  `vacuumValve.vacuumValveReadExtra`. This entity has no dlsPLC equivalent yet
  and must be manually commented out of `ioc.yaml`.

## Running hybrid mode

### In a devcontainer (local testing)

The `--instance` flag on `rtems-proxy start` extracts all necessary
environment variables from the services repo values.yaml files, symlinks the
instance config, and runs the full hybrid pipeline:

```bash
rtems-proxy start --hybrid --no-connect \
    --instance /workspaces/i19-services/services/bl19i-va-ioc-01
```

The `--instance` flag does the following automatically:
- Reads global env vars (`RTEMS_IOC_GATEWAY`, `RTEMS_IOC_NETMASK`, etc.) from
  `<instance>/../values.yaml`
- Reads instance env vars (`IOC_ORIGINAL_LOCATION`, `RTEMS_IOC_IP`, etc.) from
  `<instance>/values.yaml`
- Derives `IOC_NAME` from `IOC_ORIGINAL_LOCATION` (folder name, uppercased)
- Sets `IOC_DOMAIN` from `global.domain`
- Symlinks `<instance>/config/` into `/epics/ioc/config`

Use `--no-connect` when testing locally since there is no RTEMS crate on the
network.

### In a Kubernetes cluster

In-cluster, the environment variables are set by the Helm chart from
`values.yaml`, the instance config is mounted into `/epics/ioc/config` by
Kubernetes, and NFS/TFTP volumes are mounted at `/ioc_nfs` and `/ioc_tftp`.

The `--instance` flag is **not** used — everything comes from the environment
and volume mounts. The container command is simply:

```yaml
args:
  - |
    stdio-socket --ptty "rtems-proxy start --hybrid"
```

Without `--no-connect`, rtems-proxy will also connect to the RTEMS crate via
telnet, configure motBoot NVM variables, and boot the IOC.

### Instance `values.yaml` structure

The instance values.yaml lives at
`<services-repo>/services/<ioc-name>/values.yaml`:

```yaml
ioc-instance:
  image: ghcr.io/epics-containers/rtems-proxy-developer:2.1.0
  args:
    - |
      stdio-socket --ptty "rtems-proxy start --hybrid"

  env:
    - name: IOC_ORIGINAL_LOCATION
      value: /dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01
    - name: RTEMS_IOC_IP
      value: 172.23.119.98
    - name: RTEMS_CONSOLE
      value: BL19I-NT-TSERV-01:7002

  volumeMounts:
    - name: nfsv2
      mountPath: /ioc_nfs
      subPathExpr: $(IOC_NAME)
    - name: tftp
      mountPath: /ioc_tftp
      subPathExpr: $(IOC_NAME)
    - name: work
      mountPath: /dls_sw/work
      readOnly: true
    - name: prod
      mountPath: /dls_sw/prod
      readOnly: true

  volumes:
    - name: nfsv2
      hostPath:
        path: /dls_sw/<beamline>/epics/rtems
    - name: tftp
      persistentVolumeClaim:
        claimName: <beamline>-binaries-claim
    - name: work
      hostPath:
        path: /dls_sw/work
    - name: prod
      hostPath:
        path: /dls_sw/prod
```

Global settings shared across all IOCs on a beamline go in
`<services-repo>/services/values.yaml`:

```yaml
global:
  domain: i19
  env:
    - name: RTEMS_IOC_GATEWAY
      value: 172.23.119.254
    - name: RTEMS_IOC_NETMASK
      value: 255.255.255.0
    - name: RTEMS_NFS_IP
      value: 172.23.119.226
    - name: RTEMS_TFTP_IP
      value: 172.23.119.226
```

## What `--hybrid` does step by step

The `hybrid_prepare()` function in `rtems_proxy/hybrid.py` runs these steps
in order:

1. **Create directories** — ensures `/epics/runtime`, `/ioc_nfs`, `/ioc_tftp`
   exist (they are pre-created in the container image but may not exist in a
   devcontainer).

2. **Link instance config** (only with `--instance`) — symlinks
   `<instance>/config/` to `/epics/ioc/config` so ibek can find `ioc.yaml`.

3. **Link ibek support YAMLs** — symlinks all `*.ibek.support.yaml` files from
   `$IOC_ORIGINAL_LOCATION/ibek-support*/*/` into `/epics/ibek-defs/`. These
   define the entity types and database templates available to ibek.

4. **Run `ibek runtime generate2`** — reads `ioc.yaml` from `/epics/ioc/config`
   and produces `st.cmd` (startup script) and `ioc.subst` (substitution file)
   in `/epics/runtime/`.

5. **Run `msi`** — sources `$IOC_ORIGINAL_LOCATION/data/msi.vars` to get all
   module path macros and `MSI_INCLUDES`, then expands `ioc.subst` into
   `ioc.db` using `msi`. The macros are needed because the `.subst` file
   references templates via paths like `$(IOCSTATS)/db/iocAdminSoft.db`.

6. **Copy to NFS** — rsyncs into two subfolders that match the paths the
   crate's `st.cmd` reads once the export is mounted at `/epics`:
   `runtime/` gets `st.cmd`, `ioc.db`, the `protocol/` folder (`data/*.proto*`)
   and any autosave `*.req` files; `ioc/` gets `dbd/`.

7. **Copy binary to TFTP** — copies `$IOC_ORIGINAL_LOCATION/bin/RTEMS-beatnik/<IOC_BUILD_NAME>.boot`
   (the build-tree name, e.g. `BL-VA-IOC-01.boot`) to `/ioc_tftp/rtems.ioc.bin`.

### Manual debugging

If a step fails you can run each phase individually:

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

# 4. Verify outputs
ls /epics/runtime/st.cmd /epics/runtime/ioc.subst /epics/runtime/ioc.db
```

## Troubleshooting

### Schema validation errors from `ibek runtime generate2`

This usually means the `ioc.yaml` has fields that don't match the ibek support
YAMLs. Common causes:

- **Stale ioc.yaml** — re-run `builder2ibek` with the latest version.
- **Zero-indexed vs one-indexed fields** — older `builder2ibek` versions
  generated `ionp0`, `gauge0` etc. but the support YAMLs expect `ionp1`,
  `gauge1`. Updating `builder2ibek` fixes this.
- **Unconverted entity types** — e.g. `vacuumValve.vacuumValveReadExtra` is
  not converted by `builder2ibek`. Comment out or remove these from `ioc.yaml`.

### `msi: Can't open file` errors

The `.subst` file references DB template files via macros like
`$(DLSPLC)/db/...`. If `msi.vars` doesn't define a macro, or the module
version in `configure/RELEASE` doesn't contain the expected template, msi will
fail.

- Check that the Generic IOC's `configure/RELEASE` includes all required
  support modules.
- Rebuild the Generic IOC (`make` in its top directory) to regenerate
  `data/msi.vars` after any RELEASE changes.
- Bare template filenames (without a `$(MODULE)/db/` prefix) in the `.subst`
  file indicate a bug in the ibek support YAML — the template path should use
  the module macro.

### `macro X is undefined`

The `msi.vars` file must be sourced (not just `MSI_INCLUDES`) because the
`.subst` file uses macros like `$(IOCSTATS)` in `file` directives, not just in
`-I` include paths. rtems-proxy handles this automatically, but if running
manually, make sure to `source $IOC_ORIGINAL_LOCATION/data/msi.vars` before
invoking `msi`.

## Worked example

For an end-to-end walkthrough using a concrete instance (BL19I vacuum IOC,
from VxWorks builder XML through devcontainer testing to a cluster deploy),
see [example-bl19i-va-ioc-01.md](example-bl19i-va-ioc-01.md).
