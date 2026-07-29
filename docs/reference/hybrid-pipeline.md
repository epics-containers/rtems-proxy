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

4. **Run `ibek runtime generate2`** — reads `ioc.yaml` from `/epics/ioc/config`
   and produces `st.cmd` and `ioc.subst` in `/epics/runtime/`.

5. **Run `msi`** — sources `$IOC_ORIGINAL_LOCATION/data/msi.vars` to get all
   module path macros and `MSI_INCLUDES`, then expands `ioc.subst` into
   `ioc.db`. The macros are needed because the `.subst` file references
   templates via paths like `$(IOCSTATS)/db/iocAdminSoft.db`.

6. **Run `ibek runtime generate-autosave`** — symlinks every `*.req` file from
   `$IOC_ORIGINAL_LOCATION/ibek-support*/*/` into `/epics/autosave`, then parses
   `ioc.subst`, matches each DB template stem to its `*.req` files and expands
   them with each instance's macros (via `msi`) into the master
   `autosave_positions.req` and `autosave_settings.req` in `/epics/runtime/`.
   The generated `st.cmd` loads these via `create_monitor_set`.

7. **Copy to NFS** — rsyncs into two subfolders matching the paths the crate's
   `st.cmd` reads once the export is mounted at `/epics`: `runtime/` gets
   `st.cmd`, `ioc.db`, the `protocol/` folder (`data/*.proto*`) and any autosave
   `*.req` files; `ioc/` gets `dbd/`.

8. **Copy binary to TFTP** — copies
   `$IOC_ORIGINAL_LOCATION/bin/RTEMS-beatnik/ioc.boot` (the generic boot image
   name) to `/ioc_tftp/rtems.ioc.bin`.

Without `--no-connect`, rtems-proxy then connects to the RTEMS crate via
telnet, configures the motBoot NVM variables, and boots the IOC.

## Generated artefacts

| Path | Produced by | Contents |
| --- | --- | --- |
| `/epics/runtime/st.cmd` | step 4 | IOC startup script |
| `/epics/runtime/ioc.subst` | step 4 | substitution file |
| `/epics/runtime/ioc.db` | step 5 | expanded EPICS database |
| `/epics/runtime/autosave_*.req` | step 6 | master autosave request files |
| `/ioc_nfs/runtime/`, `/ioc_nfs/ioc/dbd/` | step 7 | what the crate NFS-mounts |
| `/ioc_tftp/rtems.ioc.bin` | step 8 | boot image the crate TFTPs |
