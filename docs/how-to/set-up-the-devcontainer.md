# Set up the devcontainer

All local hybrid work — `builder2ibek`, schema generation, hybrid prepare and
driving a crate — runs inside this repository's devcontainer, which supplies
`ibek`, `msi`, the `rtems-proxy` entry point and the `/dls_sw` mounts.

Open the `rtems-proxy` folder in VS Code and run **Dev Containers: Reopen in
Container**, or from the CLI:

```bash
devcontainer up --workspace-folder .
```

## What the mounts give you

- `/dls_sw` bound read-only, with `bind-propagation=slave` so the host's autofs
  submounts (`/dls_sw/prod`, `/dls_sw/<beamline>/epics`) are visible without
  having to trigger them from inside the container. This is what lets `msi`
  resolve the prod support-module template paths from `msi.vars`.
- `/dls_sw/work/R7.0.7/ioc/BL/` bound read-write, so you can build or tweak the
  Generic IOC in place from inside the container.
- `/workspaces` mapped to the **parent** of this repo — clone the beamline
  services repo alongside `rtems-proxy` so that
  `/workspaces/<beamline>-services/services/<ioc-name>` resolves for the
  `--instance` flag.

## Check the working directories exist

```bash
ls -d /epics/ibek-defs /epics/runtime /epics/autosave /ioc_nfs /ioc_tftp
```

These are created by the `Dockerfile`, but only since June 2026. A devcontainer
running an image built before that will be missing some of them, and both
schema generation and hybrid prepare will fail on the absent paths. If any are
missing, run **Dev Containers: Rebuild Container**.

`mkdir -p` covers the same gap if you would rather not rebuild yet, but note
that hybrid prepare also needs `/ioc_nfs` and `/ioc_tftp`, not just
`/epics/ibek-defs`.
