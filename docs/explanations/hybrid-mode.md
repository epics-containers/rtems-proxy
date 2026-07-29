# Hybrid IOCs

A hybrid IOC pairs a pre-built Generic IOC binary from the DLS build server
with ibek-generated runtime configuration, all managed by Kubernetes via
rtems-proxy. It is the quickest way to convert an existing VxWorks XmlBuilder
IOC to RTEMS5.

## The three pieces

1. **A Generic RTEMS5 IOC binary** — shared across all beamlines for a class of
   IOC (e.g. beamline vacuum). Built and released via the DLS build server to
   `/dls_sw/prod`, or run out of `/dls_sw/work`.
2. **An `ioc.yaml` instance definition** — auto-converted from the existing
   VxWorks builder XML using `builder2ibek`, living in the beamline services
   repository (e.g.
   `i19-services/services/bl19i-va-ioc-01/config/ioc.yaml`).
3. **rtems-proxy in `--hybrid` mode** — at runtime it uses ibek and `msi` to
   generate `st.cmd` and `ioc.db` from the instance definition, then places all
   assets on NFS/TFTP for the RTEMS crate to boot.

The division of labour matters: the *binary* is shared and versioned by the
build server, while the *instance* is per-IOC and lives in GitOps alongside
every other service on the beamline. Hybrid mode is the glue that lets those
two halves meet at container start-up rather than at build time.

## What makes a Generic IOC usable in hybrid mode

The Generic IOC is maintained at
<https://gitlab.diamond.ac.uk/controls/ioc/BL> as a native EPICS 7, RTEMS5 IOC.
See [confluence](https://confluence.diamond.ac.uk/x/_w6WFQ) for build details.

Beyond a standard EPICS IOC it needs a few additions.

### ibek-support submodules

`ibek-support/` and `ibek-support-dls/` are submodules of the Generic IOC, so
that ibek support YAML versions are tracked with the IOC binary version. This
is what lets a schema generated today describe exactly the binary you are about
to boot.

### A generic binary name

rtems-proxy expects the cross-compiled product to be named generically rather
than after the IOC instance, so the build emits `bin/RTEMS-beatnik/ioc` (the
binary) and `bin/RTEMS-beatnik/ioc.boot` (the boot image). To achieve this:

- rename the IOC main source `xxxMain.cpp` to `iocMain.cpp`;
- edit `src/Makefile` so the product is named `ioc`, e.g. `PROD_IOC = ioc`
  (and `ioc_SRCS += iocMain.cpp`).

### `data/msi.vars`

The top-level `Makefile` auto-generates `data/msi.vars` whenever
`configure/RELEASE` changes. It exports every module path from RELEASE as a
shell variable, plus a composite `MSI_INCLUDES` listing all `-I<module>/db`
flags:

```makefile
all: data/msi.vars

data/msi.vars: $(TOP)/configure/RELEASE
	@echo "#!/bin/bash" > $@
	@echo "# Auto-generated from configure/RELEASE" >> $@
	@$(foreach var,$(RELEASE_VARS),echo "export $(var)=$($(var))" >> $@;)
	@echo "export MSI_INCLUDES=\"$(SYS_MSI_INCLUDES)\"" >> $@
```

At hybrid runtime rtems-proxy sources this file before running `msi`, which
makes macros like `$(IOCSTATS)` and `$(DLSPLC)` available for resolving paths
in the `.subst` file. Sourcing the whole file matters: the `.subst` references
templates via macros in `file` directives, not only in `-I` include paths.

### Protocol files

The `src/Makefile` also collects all stream device protocol files into `data/`,
for easy protocol file path management:

```makefile
all_protos = $(foreach path,$(subst :, ,$(SYS_EDM_PATHS)),$(wildcard $(path)/*.proto*))
DATA += $(all_protos)
```

rtems-proxy places these on the NFS share at runtime.

## See also

- [](../reference/hybrid-pipeline.md) — what `--hybrid` does, step by step.
- [](../tutorials/hybrid-ioc-walkthrough.md) — a worked example.
