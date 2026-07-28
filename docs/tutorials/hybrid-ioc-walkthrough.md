# Convert a VxWorks IOC to a hybrid RTEMS IOC

This walks through converting one specific VxWorks XmlBuilder IOC — the BL19I
beamline vacuum IOC — into a hybrid RTEMS5 IOC: generating its `ioc.yaml` from
the existing builder XML, testing it end-to-end in a devcontainer, then handing
it to the cluster via the standard i19 GitOps deploy.

For the concepts behind this, see [](../explanations/hybrid-mode.md).

## What we are starting from

Three existing pieces, all already on `/dls_sw` and in the services repo:

- **Existing VxWorks builder XML** —
  `/dls_sw/prod/R3.14.12.7/support/BL19I-BUILDER/25-3-1/etc/makeIocs/BL19I-VA-IOC-01.xml`.
  The historical instance definition, which we convert into `ioc.yaml`.
- **Generic RTEMS5 VA IOC binary tree** —
  `/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01`, including the
  `bin/RTEMS-beatnik/ioc.boot` boot image, the `ibek-support*/` submodules, and
  the auto-generated `data/msi.vars`.
- **Target services-repo instance folder** —
  `/workspaces/i19-services/services/bl19i-va-ioc-01`, holding `values.yaml`
  and `config/ioc.yaml`.

## Step 1 — Launch the devcontainer

Everything from here runs inside the rtems-proxy devcontainer. Open it, and
check the hybrid working directories exist:

```bash
ls -d /epics/ibek-defs /epics/runtime /epics/autosave /ioc_nfs /ioc_tftp
```

If any are missing, rebuild the container — see
[](../how-to/set-up-the-devcontainer.md). Clone `i19-services` alongside
`rtems-proxy` under `/workspaces` so the `--instance` path in step 4 resolves.

## Step 2 — Create the instance in i19-services

If the folder does not yet exist, create the minimal layout alongside the
shared beamline-wide `services/values.yaml` that is already in the repo:

```text
services/
├── values.yaml                  # beamline-wide globals, shared by every i19 IOC
└── bl19i-va-ioc-01/
    ├── values.yaml              # this instance's settings
    └── config/
        └── ioc.yaml             # filled in by step 3
```

The beamline globals supply `domain` plus four RTEMS values
(`RTEMS_IOC_GATEWAY`, `RTEMS_IOC_NETMASK`, `RTEMS_NFS_IP`, `RTEMS_TFTP_IP`);
the instance file supplies `IOC_ORIGINAL_LOCATION`, `RTEMS_IOC_IP`,
`RTEMS_CONSOLE` and the volume mounts. Both files are given in full in
[](../reference/configuration.md) — copy them from there and change the
beamline-specific values.

## Step 3 — Convert the builder XML

```bash
uvx builder2ibek xml2yaml \
    --yaml /workspaces/i19-services/services/bl19i-va-ioc-01/config/ioc.yaml \
    /dls_sw/prod/R3.14.12.7/support/BL19I-BUILDER/25-3-1/etc/makeIocs/BL19I-VA-IOC-01.xml
```

Then generate the validation schema so your editor checks the file as you edit:

```bash
export IOC_ORIGINAL_LOCATION=/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01

mkdir -p /epics/ibek-defs
ibek ioc generate-schema --no-ibek-defs \
    --output /epics/ibek-defs/ioc.schema.json \
    $IOC_ORIGINAL_LOCATION/ibek-support/*/*.ibek.support.yaml \
    $IOC_ORIGINAL_LOCATION/ibek-support-dls/*/*.ibek.support.yaml
```

For the vacuum IOC, the `vacuumValve.vacuumValveReadExtra` entity is the usual
snag — `builder2ibek` has no equivalent and the generated entry must be
commented out before the next step. See
[](../how-to/convert-builder-xml.md) for the other known quirks and for
command-line validation.

## Step 4 — Test in the devcontainer

Run hybrid prepare on its own, with no console connection and no real crate:

```bash
rtems-proxy start --hybrid --no-connect \
    --instance /workspaces/i19-services/services/bl19i-va-ioc-01
```

`--instance` reads the two `values.yaml` files from step 2, exports the
environment (including `IOC_NAME=bl19i-va-ioc-01`, from the services instance
folder name — distinct from the build-tree name `bl-va-ioc-01`), and symlinks
`config/` into `/epics/ioc/config`.

A successful run prints the progress lines listed in
[](../reference/hybrid-pipeline.md), and the artefacts should exist:

```bash
ls /epics/runtime/st.cmd /epics/runtime/ioc.subst /epics/runtime/ioc.db
ls /ioc_nfs/runtime/st.cmd /ioc_nfs/runtime/ioc.db /ioc_nfs/ioc/dbd
ls /ioc_tftp/rtems.ioc.bin
```

The boot image is copied from
`/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01/bin/RTEMS-beatnik/ioc.boot`, so make
sure the Generic IOC has been built there first.

If a step fails, [](../how-to/troubleshoot-hybrid.md) has the per-step manual
commands and the matching fixes.

## Step 5 — Connect to the real crate

Before the crate can boot, the `.boot` image must reach the real i19 TFTP
server and the generated runtime must reach the NFS export. Both are manual
from a devcontainer and are covered in
[](../how-to/run-hybrid-mode.md#drive-a-real-crate-from-the-devcontainer).

With those in place, drop `--no-connect` to drive the actual BL19I crate:

```bash
rtems-proxy start --hybrid \
    --instance /workspaces/i19-services/services/bl19i-va-ioc-01
```

## Step 6 — Deploy to the cluster

Commit `values.yaml` and `config/ioc.yaml`, push the branch, and — for a
brand-new instance only — bootstrap argocd once with
`ec deploy bl19i-va-ioc-01 <branch-name>`. See
[](../how-to/deploy-to-kubernetes.md).
