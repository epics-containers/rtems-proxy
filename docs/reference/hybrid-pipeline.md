# The hybrid pipeline

`hybrid_prepare()` in `src/rtems_proxy/hybrid.py` runs these steps in order.
Each prints a progress line, so the log tells you how far it got.

1. **Create directories** — ensures `/epics/runtime`, `/ioc_nfs` and
   `/ioc_tftp` exist. They are pre-created in the container image, but may not
   be in an older devcontainer.

2. **Link instance config** (only with `--instance`) — symlinks
   `<instance>/config/` to `/epics/ioc/config` so ibek can find `ioc.yaml`.

3. **Link ibek support YAMLs** — symlinks all `*.ibek.support.yaml` files from
   `$IOC_ORIGINAL_LOCATION/ibek-support*/*/` into `/epics/ibek-defs/`. These
   define the entity types and database templates available to ibek.

4. **Warn on latent macro mismatches** (advisory) — scans the YAMLs linked in
   step 3 for `$(MACRO)/db/` paths whose macro `msi.vars` does not define while
   the module *is* defined under another name. Never fails: these modules are
   not instantiated by this IOC, so nothing breaks today. See
   [](./macro-checks.md).

5. **Run `ibek runtime generate2`** — reads `ioc.yaml` from `/epics/ioc/config`
   and produces `st.cmd` and `ioc.subst` in `/epics/runtime/`.

6. **Check subst macros** (fatal) — every `$(MACRO)` in a `file "..."` line of
   the generated `ioc.subst` must be defined in `msi.vars`. Anything reported
   here is a macro msi is about to fail on, so the run stops with the module,
   the macro and the name the build actually uses, rather than the bare
   `msi expansion failed` that msi alone produces.

7. **Run `msi`** — sources `$IOC_ORIGINAL_LOCATION/data/msi.vars` to get all
   module path macros and `MSI_INCLUDES`, then expands `ioc.subst` into
   `ioc.db`. The macros are needed because the `.subst` file references
   templates via paths like `$(IOCSTATS)/db/iocAdminSoft.db`.

8. **Run `ibek runtime generate-autosave`** — symlinks every `*.req` file from
   `$IOC_ORIGINAL_LOCATION/ibek-support*/*/` into `/epics/autosave`, then parses
   `ioc.subst`, matches each DB template stem to its `*.req` files and expands
   them with each instance's macros (via `msi`) into the master
   `autosave_positions.req` and `autosave_settings.req` in `/epics/runtime/`.
   The generated `st.cmd` loads these via `create_monitor_set`.

9. **Copy to NFS** — rsyncs into two subfolders matching the paths the crate's
   `st.cmd` reads once the export is mounted at `/epics`: `runtime/` gets
   `st.cmd`, `ioc.db`, the `protocol/` folder (`data/*.proto*`) and any autosave
   `*.req` files; `ioc/` gets `dbd/`.

10. **Copy binary to TFTP** — copies
   `$IOC_ORIGINAL_LOCATION/bin/RTEMS-beatnik/ioc.boot` (the generic boot image
   name) to `/ioc_tftp/rtems.ioc.bin`.

Without `--no-connect`, rtems-proxy then connects to the RTEMS crate via
telnet, configures the motBoot NVM variables, and boots the IOC.

## Generated artefacts

| Path | Produced by | Contents |
| --- | --- | --- |
| `/epics/runtime/st.cmd` | step 5 | IOC startup script |
| `/epics/runtime/ioc.subst` | step 5 | substitution file |
| `/epics/runtime/ioc.db` | step 7 | expanded EPICS database |
| `/epics/runtime/autosave_*.req` | step 8 | master autosave request files |
| `/ioc_nfs/runtime/`, `/ioc_nfs/ioc/dbd/` | step 9 | what the crate NFS-mounts |
| `/ioc_tftp/rtems.ioc.bin` | step 10 | boot image the crate TFTPs |
