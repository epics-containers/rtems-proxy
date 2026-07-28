# Run hybrid mode locally

Run the hybrid prepare pipeline in the devcontainer, without a real crate:

```bash
rtems-proxy start --hybrid --no-connect \
    --instance /workspaces/i19-services/services/bl19i-va-ioc-01
```

`--instance` extracts the environment from the services repo `values.yaml`
files and symlinks the instance config into place — see
[](../reference/configuration.md#what-the-instance-flag-does). Use `--no-connect` when
testing locally, since there is no RTEMS crate on the network.

A successful run prints the progress lines from
[](../reference/hybrid-pipeline.md). Check the artefacts landed:

```bash
ls /epics/runtime/st.cmd /epics/runtime/ioc.subst /epics/runtime/ioc.db
ls /ioc_nfs/runtime/st.cmd /ioc_nfs/runtime/ioc.db /ioc_nfs/ioc/dbd
ls /ioc_tftp/rtems.ioc.bin
```

The boot image is copied from
`$IOC_ORIGINAL_LOCATION/bin/RTEMS-beatnik/ioc.boot`, so the Generic IOC must
have been built there first.

## Drive a real crate from the devcontainer

Two things have to reach the real servers before the crate can boot. Neither is
needed in a cluster, where the proxy pod writes to both directly.

### Push the boot binary to TFTP (one-off, from the workstation)

The devcontainer cannot mount a cluster PVC, so this step is done **outside**
it, from a workstation. The namespace runs a long-lived pod that mounts the
TFTP PVC without a `subPath` for exactly this purpose. `module load` provides
`ec` and points `kubectl` at the beamline's cluster context and namespace:

```bash
# 1. find the uploader pod
module load ec/i19
TFTP_POD=$(kubectl get pods -o name | grep tftp)

# 2. copy the binary straight from /dls_sw into the uploader pod
#    (source is the generic ioc.boot; destination must be rtems.ioc.bin,
#    because that is the name motBoot will request)
kubectl cp \
    /dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01/bin/RTEMS-beatnik/ioc.boot \
    ${TFTP_POD#pod/}:/iocs/bl19i-va-ioc-01/rtems.ioc.bin
```

Adjust the destination to match the uploader pod's PVC layout (typically one
subdirectory per `IOC_NAME` at the PVC root).

### Push the runtime files to NFS (repeat on every change)

At boot the crate NFS-mounts its per-IOC export —
`/dls_sw/<beamline>/epics/rtems/<ioc-name>` — at `/epics`, and reads `st.cmd`,
`ioc.db`, `protocol/` and `dbd/` from there. In the devcontainer the proxy
wrote to the local `/ioc_nfs` scratch dir instead, so those files must be
pushed onto the real export by hand.

Unlike the TFTP binary push, this **repeats every time the generated runtime
changes** — edit `ioc.yaml`, touch a support template, or otherwise alter
`st.cmd`/`ioc.db`, and you must regenerate and copy again.

Empty the target first. A previous run — or the old flat layout — can leave
stale files behind (most dangerously an old `st.cmd` still pointing at the
retired `/epics_rtems_root` mount), and the crate will happily boot whatever is
there:

```bash
rm -rf /dls_sw/i19/epics/rtems/bl19i-va-ioc-01/*
cp -a /ioc_nfs/. /dls_sw/i19/epics/rtems/bl19i-va-ioc-01/
```

```{note}
**Split access — a known rough edge.** No single shell has both ends: inside
the devcontainer you have the source (`/ioc_nfs`) but `/dls_sw` is mounted
read-only, while on the workstation you have write access to `/dls_sw/i19/...`
but not the devcontainer-internal `/ioc_nfs`. Until the devcontainer is given a
read-write mount of the per-IOC export (or an NFS uploader pod is set up the
way the TFTP one is), you have to bridge the two — stage `/ioc_nfs` out to a
shared path the workstation can reach, then run the `rm`/`cp` there.
```

### Connect

With the binary in place, drop `--no-connect`:

```bash
rtems-proxy start --hybrid \
    --instance /workspaces/i19-services/services/bl19i-va-ioc-01
```

rtems-proxy telnets to `RTEMS_CONSOLE`, drops the crate into motBoot, sets the
NVM variables to point at the NFS and TFTP locations, reboots the crate, and
attaches the container stdio to the IOC shell so you see the boot log live.
This needs the devcontainer to be on a network that can reach the terminal
server.
