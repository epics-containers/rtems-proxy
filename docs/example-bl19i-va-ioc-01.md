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
  will boot from this binary and use its ibek support YAMLs.
- **Target services-repo instance folder** —
  `/workspaces/i19-services/services/bl19i-va-ioc-01`. The Helm values and
  config for this instance, holding both the `values.yaml` (env vars and
  volume mounts) and `config/ioc.yaml` (the ibek instance description).

## Step 1 — Create the instance in i19-services

If the folder does not yet exist, create the minimal layout:

```
services/bl19i-va-ioc-01/
├── values.yaml
└── config/
    └── ioc.yaml    # filled in by step 2
```

`services/bl19i-va-ioc-01/values.yaml` for this instance:

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
        path: /dls_sw/i19/epics/rtems
    - name: tftp
      persistentVolumeClaim:
        claimName: i19-binaries-claim
    - name: work
      hostPath:
        path: /dls_sw/work
    - name: prod
      hostPath:
        path: /dls_sw/prod
```

The beamline-wide settings (`RTEMS_IOC_GATEWAY`, `RTEMS_IOC_NETMASK`,
`RTEMS_NFS_IP`, `RTEMS_TFTP_IP`, `global.domain: i19`) live one level up in
`services/values.yaml` and are shared with the other i19 IOCs — there is
nothing instance-specific to add there for this example.

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

Open the rtems-proxy developer container attached to the
`/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01` generic IOC tree, then run the
hybrid prepare step on its own (no console connection, no real crate):

```bash
rtems-proxy start --hybrid --no-connect \
    --instance /workspaces/i19-services/services/bl19i-va-ioc-01
```

The `--instance` flag reads the two `values.yaml` files you set up in step 1,
exports all the env vars (including `IOC_NAME=BL-VA-IOC-01` derived from
`IOC_ORIGINAL_LOCATION`), and symlinks `config/` into `/epics/ioc/config`. A
successful run prints the seven progress lines from `hybrid_prepare()` in
`src/rtems_proxy/hybrid.py`:

1. `Linked instance config .../bl19i-va-ioc-01/config -> /epics/ioc/config`
2. `Linked N ibek support YAMLs into /epics/ibek-defs`
3. `Running: ibek runtime generate2 /epics/ioc/config --no-pvi`
4. `ibek generate2 completed`
5. `Running msi` → `msi expansion completed`
6. `Placed runtime files in /ioc_nfs`
7. `Placed IOC binary at /ioc_tftp/rtems.ioc.bin`

After the run, the generated artefacts should exist:

```bash
ls /epics/runtime/st.cmd /epics/runtime/ioc.subst /epics/runtime/ioc.db
ls /ioc_nfs/st.cmd /ioc_nfs/ioc.db
ls /ioc_tftp/rtems.ioc.bin
```

The boot image is copied from
`/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01/bin/RTEMS-beatnik/BL-VA-IOC-01.boot`,
so make sure the generic IOC has been built there before running this step.

If any of the seven steps fail, `hybrid.md` has the per-step manual
incantations under [Manual debugging](hybrid.md#manual-debugging) and the
matching fixes under [Troubleshooting](hybrid.md#troubleshooting).

## Step 4 — Connect to the real crate from the devcontainer

Once the prepare stage is clean, drop `--no-connect` to drive the actual
BL19I crate:

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
2. Push the branch and open the merge request.
3. After merge, the existing i19 GitOps pipeline (argocd / beamline-chart
   sync) renders the Helm chart and deploys the proxy pod. The container
   starts with the args from `values.yaml` —
   `rtems-proxy start --hybrid` with no `--instance` flag, because the env
   vars are now coming from the Helm-rendered env block and the config is
   mounted into `/epics/ioc/config` by Kubernetes. See
   [hybrid.md — In a Kubernetes cluster](hybrid.md#in-a-kubernetes-cluster)
   for the values.yaml shape that drives this.
4. Verify by tailing the proxy-pod logs in the cluster — the same seven
   progress lines from step 3 should appear, followed by the motboot
   configuration, reboot, and the live console.

## Where to go next

- [hybrid.md](hybrid.md) — full hybrid-mode reference and troubleshooting.
- [overview.md](overview.md) — the three deployment flavours for RTEMS IOCs
  at DLS and where hybrid sits among them.
