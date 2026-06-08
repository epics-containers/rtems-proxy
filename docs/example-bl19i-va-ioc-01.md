# Worked example: hybrid IOC for bl19i-va-ioc-01

This page walks through converting one specific VxWorks XmlBuilder IOC — the
BL19I beamline vacuum IOC — into a hybrid RTEMS5 IOC: generating its
`ioc.yaml` from the existing builder XML, testing it end-to-end in a
devcontainer, and then handing it off to the cluster via the standard i19
GitOps deploy.

For the conceptual overview of hybrid mode and the full reference for each
moving part, see [hybrid.md](hybrid.md). This page is the tutorial companion.

## What we're starting from

Three existing pieces, all already on `/dls_sw` and in the services repo:

- **Existing VxWorks builder XML** —
  `/dls_sw/prod/R3.14.12.7/support/BL19I-BUILDER/25-3-1/etc/makeIocs/BL19I-VA-IOC-01.xml`.
  The historical instance definition. We will convert this into `ioc.yaml`.
- **Generic RTEMS5 VA IOC binary tree** —
  `/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01`. The pre-built Generic IOC for
  beamline vacuum, including the `bin/RTEMS-beatnik/BL-VA-IOC-01.boot` binary,
  the `ibek-support*/` submodules, and the auto-generated `data/msi.vars`. We
  will boot from this binary and use its ibek support YAMLs. See
  [hybrid.md — The Generic IOC](hybrid.md#the-generic-ioc) for the special
  additions that make a Generic IOC usable in hybrid mode, and
  [epics-containers — Generic IOCs and Instances](https://epics-containers.github.io/main/explanations/introduction.html#generic-iocs-and-instances)
  for the broader Generic-IOC concept.
- **Target services-repo instance folder** —
  `/workspaces/i19-services/services/bl19i-va-ioc-01`. The Helm values and
  config for this instance, holding both the `values.yaml` (env vars and
  volume mounts) and `config/ioc.yaml` (the ibek instance description).

## Step 1 — Create the instance in i19-services

If the folder does not yet exist, create the minimal layout — alongside the
shared beamline-wide `services/values.yaml` that already exists in the repo:

```
services/
├── values.yaml                  # beamline-wide globals, shared by every i19 IOC
└── bl19i-va-ioc-01/
    ├── values.yaml              # this instance's settings
    └── config/
        └── ioc.yaml             # filled in by step 2
```

### Beamline-wide globals — `services/values.yaml`

These RTEMS values are for  all i19 RTEMS IOCs on the
beamline.

There are four RTEMS-related entries (plus the domain key that `_load_instance_env` reads) which look like this:

```yaml
global:
  # beamline or accelerator technical area
  domain: i19
  env:
    # default gateway written into the crate's motBoot NVM at configure time
    - name: RTEMS_IOC_GATEWAY
      value: 172.23.119.254
    # subnet mask written into motBoot NVM
    - name: RTEMS_IOC_NETMASK
      value: 255.255.255.0
    # NFS server the crate mounts /ioc_nfs from at boot
    - name: RTEMS_NFS_IP
      value: 172.23.119.226
    # TFTP server the crate fetches its .boot image from
    - name: RTEMS_TFTP_IP
      value: 172.23.119.226
```

### Instance settings — `services/bl19i-va-ioc-01/values.yaml`

This is the file you create for the new instance:

```yaml
ioc-instance:
  # proxy + ibek + msi runtime image (epics-containers registry)
  image: ghcr.io/epics-containers/rtems-proxy-developer:2.1.0
  args:
    # container command: hybrid-mode rtems-proxy wrapped in stdio-socket
    - |
      stdio-socket --ptty "rtems-proxy start --hybrid"

  env:
    # generic IOC build tree — source of ibek-support YAMLs, msi.vars and the .boot binary
    - name: IOC_ORIGINAL_LOCATION
      value: /dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01
    # static IP the crate is given via BOOTP/DHCP by MAC address
    - name: RTEMS_IOC_IP
      value: 172.23.119.98
    # terminal-server host:port for the crate's serial console (telnet)
    - name: RTEMS_CONSOLE
      value: BL19I-NT-TSERV-01:7002

  volumeMounts:
    # rtems-proxy writes runtime assets here; crate mounts the same dir via NFSv2
    - name: nfsv2
      mountPath: /ioc_nfs
      # one subdir per IOC under the shared beamline NFS export
      subPathExpr: $(IOC_NAME)
    # rtems-proxy drops the .boot binary here; TFTP server publishes it to the crate
    - name: tftp
      mountPath: /ioc_tftp
      subPathExpr: $(IOC_NAME)
    # read-only DLS work area — needed to read the generic IOC tree
    - name: work
      mountPath: /dls_sw/work
      readOnly: true
    # read-only DLS prod area — msi reads support-module DB templates from here
    - name: prod
      mountPath: /dls_sw/prod
      readOnly: true

  volumes:
    - name: nfsv2
      hostPath:
        # i19 NFS export root for RTEMS IOCs
        path: /dls_sw/i19/epics/rtems
    - name: tftp
      persistentVolumeClaim:
        # shared PVC backing the i19 TFTP server
        claimName: i19-binaries-claim
    - name: work
      hostPath:
        # cluster-node bind-mount of the DLS work area
        path: /dls_sw/work
    - name: prod
      hostPath:
        # cluster-node bind-mount of the DLS prod area
        path: /dls_sw/prod
```

## Step 2 — Convert the builder XML to ioc.yaml

Run `builder2ibek` against the prod XML to produce `config/ioc.yaml`:

```bash
uvx builder2ibek xml2yaml \
    --yaml /workspaces/i19-services/services/bl19i-va-ioc-01/config/ioc.yaml \
    /dls_sw/prod/R3.14.12.7/support/BL19I-BUILDER/25-3-1/etc/makeIocs/BL19I-VA-IOC-01.xml
```

Add the schema header at the top of `ioc.yaml` so the YAML language server
will validate it as you edit:

```yaml
# yaml-language-server: $schema=/epics/ibek-defs/ioc.schema.json
```

Generate that schema once inside the devcontainer with:

```bash
ibek ioc generate-schema --output /epics/ibek-defs/ioc.schema.json
```

For the vacuum IOC, the `vacuumValve.vacuumValveReadExtra` entity is the
usual snag — `builder2ibek` has no equivalent for it and the generated entry
must be commented out before the next step. See
[hybrid.md — Known builder2ibek issues](hybrid.md#known-builder2ibek-issues)
for the full list of conversion quirks.

## Step 3 — Test in a devcontainer

Open this repository's devcontainer (`.devcontainer/devcontainer.json`). Its
mounts give you exactly what hybrid mode needs:

- `/dls_sw` bound read-only — so `msi` can resolve the prod support-module
  template paths referenced from `msi.vars`.
- `/dls_sw/work/R7.0.7/ioc/BL/` bound read-write — the working area for the
  BL generic IOCs, where you can build or tweak `bl-va-ioc-01` in place from
  inside the container.
- `/workspaces` mapped to the parent of this repo — clone `i19-services`
  alongside `rtems-proxy` here so that
  `/workspaces/i19-services/services/bl19i-va-ioc-01` resolves for the
  `--instance` flag below.

Then run the hybrid prepare step on its own (no console connection, no real
crate):

```bash
rtems-proxy start --hybrid --no-connect \
    --instance /workspaces/i19-services/services/bl19i-va-ioc-01
```

The `--instance` flag reads the two `values.yaml` files you set up in step 1,
exports all the env vars (including `IOC_NAME=bl19i-va-ioc-01`, taken from the
services instance folder name — distinct from the build-tree name
`bl-va-ioc-01` that `IOC_BUILD_NAME` derives from `IOC_ORIGINAL_LOCATION` to
locate the `BL-VA-IOC-01.boot` binary), and symlinks `config/` into
`/epics/ioc/config`. A successful run prints the seven progress lines from
`hybrid_prepare()` in `src/rtems_proxy/hybrid.py`:

1. `Linked instance config .../bl19i-va-ioc-01/config -> /epics/ioc/config`
2. `Linked N ibek support YAMLs into /epics/ibek-defs`
3. `Running: ibek runtime generate2 /epics/ioc/config --no-pvi`
4. `ibek generate2 completed`
5. `Running msi` → `msi expansion completed`
6. `Placed runtime files in /ioc_nfs/runtime and /ioc_nfs/ioc`
7. `Placed IOC binary at /ioc_tftp/rtems.ioc.bin`

After the run, the generated artefacts should exist, laid out under the two
subfolders the crate's `st.cmd` expects once the export is mounted at `/epics`
(`runtime/` for `st.cmd`, `ioc.db` and `protocol/`; `ioc/dbd/` for the dbd):

```bash
ls /epics/runtime/st.cmd /epics/runtime/ioc.subst /epics/runtime/ioc.db
ls /ioc_nfs/runtime/st.cmd /ioc_nfs/runtime/ioc.db /ioc_nfs/ioc/dbd
ls /ioc_tftp/rtems.ioc.bin
```

The boot image is copied from
`/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01/bin/RTEMS-beatnik/BL-VA-IOC-01.boot`,
so make sure the generic IOC has been built there before running this step.

If any of the seven steps fail, `hybrid.md` has the per-step manual
incantations under [Manual debugging](hybrid.md#manual-debugging) and the
matching fixes under [Troubleshooting](hybrid.md#troubleshooting).

## Step 4 — Connect to the real crate from the devcontainer

### Push the boot binary to TFTP first (one-off, from the workstation)

Before the crate can boot, the rebuilt `.boot` image has to land on the real
i19 TFTP server. In cluster mode this is automatic — the proxy pod mounts
the `i19-binaries-claim` PVC directly — but the devcontainer cannot mount a
cluster PVC, so this one step must be done **outside the devcontainer**,
from your workstation where `kubectl` and the cluster credentials live.

The i19 namespace already runs a long-lived pod that mounts the TFTP PVC
without a `subPath`, exactly for this purpose. From the workstation:

```bash
# 1. find the uploader pod
module load ec/i19
TFTP_POD=$(kubectl get pods -o name | grep tftp)

# 2. copy the binary straight from /dls_sw into the uploader pod
#    (source filename is BL-VA-IOC-01.boot, destination must be rtems.ioc.bin
#    because that's the name motBoot will request)
kubectl cp \
    /dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01/bin/RTEMS-beatnik/BL-VA-IOC-01.boot \
    ${TFTP_POD#pod/}:/iocs/bl19i-va-ioc-01/rtems.ioc.bin
```

Adjust the destination path to match the uploader pod's PVC mount layout
(typically one subdirectory per `IOC_NAME` at the PVC root).

### Push the runtime files to NFS (filesystem copy, repeat on every change)

The boot binary is only half of it. At boot the crate also NFS-mounts its
per-IOC runtime export — `/dls_sw/i19/epics/rtems/bl19i-va-ioc-01` — at
`/epics`, and reads `st.cmd`, `ioc.db`, `protocol/` and `dbd/` from there. In
cluster mode the proxy writes straight into that export, because the `nfsv2`
volume's `hostPath` is `/dls_sw/i19/epics/rtems` with `subPathExpr:
$(IOC_NAME)`. In the devcontainer the proxy instead wrote to the local
`/ioc_nfs` scratch dir, so those files have to be pushed onto the real export
by hand.

Unlike the TFTP binary push — which only repeats when you rebuild the `.boot`
image — this copy has to be **redone every time the generated runtime changes**:
edit the `ioc.yaml`, touch a support template, or otherwise alter `st.cmd`,
`ioc.db` or the protocol/dbd files, and you must regenerate (step 3) and copy
again before the crate will see it.

**Empty the target first.** The runtime tree is now laid out as `runtime/`
and `ioc/` subfolders; a previous run — or the old flat layout — can leave
stale files behind (most dangerously an old `st.cmd` still pointing at the
retired `/epics_rtems_root` mount), and the crate will happily boot whatever
is there. Wipe the folder before copying so nothing stale survives:

```bash
# from somewhere with write access to the export (see the caveat below)
rm -rf /dls_sw/i19/epics/rtems/bl19i-va-ioc-01/*
cp -a /ioc_nfs/. /dls_sw/i19/epics/rtems/bl19i-va-ioc-01/
```

> **Caveat — split access.** This copy is awkward because no single shell
> has both ends: inside the devcontainer you have the source (`/ioc_nfs`) but
> `/dls_sw` is mounted **read-only**, while on the workstation you have write
> access to `/dls_sw/i19/...` but not the devcontainer-internal `/ioc_nfs`.
> Until the devcontainer is given a read-write mount of the per-IOC export (or
> an NFS uploader pod is set up the way the TFTP one is), you have to bridge
> the two — e.g. stage `/ioc_nfs` out to a shared path the workstation can
> reach, then run the `rm`/`cp` there. This is a known rough edge.

### Drive the crate

Once the binary is in place on TFTP, drop `--no-connect` back in the
devcontainer to drive the actual BL19I crate:

```bash
rtems-proxy start --hybrid \
    --instance /workspaces/i19-services/services/bl19i-va-ioc-01
```

rtems-proxy will telnet into `BL19I-NT-TSERV-01:7002` (from the instance
`values.yaml`), drop the crate into motBoot, set the NVM variables to point
at the NFS and TFTP locations from the global values, reboot the crate, and
then attach the container stdio to the IOC shell so you see the boot log
live. This requires the devcontainer to be on a network that can reach the
terminal server.

## Step 5 — Deploy to the cluster

The cluster path is identical to any other i19 service — no extra rtems-proxy
machinery is involved at deploy time:

1. Commit the two new files in the i19-services repo:
   - `services/bl19i-va-ioc-01/values.yaml`
   - `services/bl19i-va-ioc-01/config/ioc.yaml`
2. Push the branch.
3. If this is a brand-new instance, argocd does not yet know about it.
   Bootstrap it once from the branch with:
   ```bash
   ec deploy bl19i-va-ioc-01 <branch-name>
   ```
   On subsequent updates this manual step is not needed — argocd picks up
   changes to the existing instance automatically.
4. Each time you push changes to the feature branch the
   existing i19 GitOps pipeline (argocd / beamline-chart sync) renders the
   Helm chart and deploys the proxy pod. The container starts with the args
   from `values.yaml` — `rtems-proxy start --hybrid` with no `--instance`
   flag, because the env vars are now coming from the Helm-rendered env
   block and the config is mounted into `/epics/ioc/config` by Kubernetes.
   See [hybrid.md — In a Kubernetes cluster](hybrid.md#in-a-kubernetes-cluster)
   for the values.yaml shape that drives this.
5. Verify by tailing the proxy-pod logs in the cluster — the same seven
   progress lines from step 3 should appear, followed by the motboot
   configuration, reboot, and the live console.

## Where to go next

- [hybrid.md](hybrid.md) — full hybrid-mode reference and troubleshooting.
- [overview.md](overview.md) — the three deployment flavours for RTEMS IOCs
  at DLS and where hybrid sits among them.
