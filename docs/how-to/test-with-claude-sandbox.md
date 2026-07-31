# Test hybrid mode under claude-sandbox

[claude-sandbox](https://github.com/DiamondLightSource/claude-sandbox) confines
`claude` to a bind-mounted set of directories. Hybrid mode writes outside the
workspace, so those paths must be granted or the run fails partway through the
pipeline.

## Install

Clone the repo and run its installer — this installs claude-sandbox itself,
which from then on wraps every `claude` launch on the host:

```bash
cd /tmp && rm -rf claude-sandbox && git clone https://github.com/DiamondLightSource/claude-sandbox && claude-sandbox/install
```

See the [claude-sandbox documentation](https://diamondlightsource.github.io/claude-sandbox/)
for everything beyond the RTEMS-specific configuration below.

## Configuration

Edit `claude-sandbox.conf` in your sandbox clone, then re-run `./install` to
copy it to `/etc/claude-sandbox.conf` (a devcontainer rebuild does this for
you). Comments are stripped here for brevity:

```ini
allow-write = /cache
allow-write = /workspaces/rtems-proxy
allow-write = /workspaces/i15-services
allow-write = /epics
allow-write = /ioc_nfs
allow-write = /ioc_tftp
allow-ip = 172.23.142.119
```

Why each write path is needed, by [pipeline](../reference/hybrid-pipeline.md)
step: `/epics` for steps 1–8 (`runtime/`, `ioc/config`, `ibek-defs/`,
`autosave/`), `/ioc_nfs` for step 9 and `/ioc_tftp` for step 10. Swap the
services repo for the beamline you are working on.

Nothing is needed for reads: `IOC_ORIGINAL_LOCATION` (`/dls_sw/work/...`, the
generic IOC build tree read throughout) and `/dls_sw/prod` are already readable
in the sandbox.

## Worked example: the i15 vacuum IOC

With the paths granted, ask Claude to run the pipeline itself so it can
diagnose what goes wrong — read the failure, inspect the generated files, fix,
re-run:

> Run `rtems-proxy start --hybrid --no-connect --instance
> /workspaces/i15-services/services/bl15i-va-ioc-01` and diagnose any failures.

`--instance` reads the instance and beamline `values.yaml`, so
`IOC_ORIGINAL_LOCATION`, `RTEMS_IOC_IP` and the rest are set for you — no
exports needed. `--no-connect` stops after the assets are staged, which is what
you want when testing generation rather than booting a crate.

This is the whole point of the write grants — each one gates a different part of
the run, so a missing grant fails at a different place: without `/epics` the run
cannot get past steps 1–8, without `/ioc_nfs` it fails at step 9, and without
`/ioc_tftp` at step 10. In every case Claude stops short of the artefacts it
needs to inspect.

:::{note}
`msi` is invoked by bare name, so steps 7 and 8 fail with `msi expansion
failed` unless `/epics/epics-base/bin/linux-x86_64` is on `PATH`. The sandbox
sets `PATH` itself and ignores `pass-env` for it, so prefix the command:

```bash
PATH=/epics/epics-base/bin/linux-x86_64:$PATH \
  rtems-proxy start --hybrid --no-connect \
  --instance /workspaces/i15-services/services/bl15i-va-ioc-01
```
:::

## Connecting to a crate

Dropping `--no-connect` needs the crate reachable. The egress jail blackholes
RFC1918, so add the crate and its terminal server from the instance
`values.yaml` (`RTEMS_IOC_IP`, `RTEMS_CONSOLE`) — for bl15i-va-ioc-01:

```ini
allow-ip = 172.23.115.98
```
