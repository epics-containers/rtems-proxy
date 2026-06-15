---
name: rtems-hybrid-debug
description: >-
  Debugging recipes for hybrid RTEMS5 IOCs driven by rtems-proxy — inspecting
  cross-compiled IOC binary symbols from a Linux box, the ibek st.cmd <-> NFS
  layout contract, and telling "not linked" apart from "not iocsh-registered".
  Use when an RTEMS IOC boots but a st.cmd command is "not found", PVs are
  missing, or boot paths look wrong.
---

# Debugging hybrid RTEMS5 IOCs

Context: rtems-proxy generates an IOC's runtime (ibek + msi), places it on
NFS/TFTP, and drives a VME crate via motBoot. The crate NFS-mounts its per-IOC
export at `/epics` and TFTP-boots a PowerPC `.boot` image. Most "it boots but
doesn't work" failures are in the **Generic IOC build** or the
**path/layout contract**, not the instance `ioc.yaml`.

## Inspecting symbols in the RTEMS IOC binary (from any Linux box)

The build tree (`.../ioc/<gen-ioc>/bin/RTEMS-beatnik/`) holds two files:

- `<IOC>` (no extension, large, e.g. 31 MB) — **unstripped ELF, has `.symtab`**.
  This is the one to inspect.
- `<IOC>.boot` (small, e.g. 3.9 MB) — stripped boot image TFTP'd to the crate.
  No symbols.

Stock RHEL8 `binutils` reads the cross-compiled `ELF32 PowerPC` image fine —
`readelf`/`nm` symbol listing is target-independent, so **no PowerPC
cross-toolchain is needed** (only `objdump -d` disassembly would need it).
`file` may be absent on DLS boxes; use `readelf -h` to confirm arch.

```bash
F=.../bin/RTEMS-beatnik/<IOC>          # the no-extension ELF, NOT .boot
readelf -h "$F" | grep -E 'Class|Machine'   # ELF32 / PowerPC
nm "$F" | grep -i <symbol>                   # is it linked at all?
nm "$F" | grep ' [Tt] '                      # all defined functions
```

## "not linked" vs "not iocsh-registered" — the key distinction

A st.cmd line like `DLS8516Configure(...)` failing with **"not found"** does
NOT necessarily mean the function is missing. An iocsh command needs more than
the function symbol — the module must also export an iocsh **registrar**.
Look for the registration machinery EPICS generates per command:

- `T <Func>`                      — the C function (callable from code)
- `t <Func>CallFunc`, `d <Func>FuncDef`, `d <Func>InitArg*` — the iocsh wrapper
- `t <Func>Register` + `D pvar_func_<Func>Register` — the `epicsExportRegistrar`

Three outcomes:
1. **Function symbol absent** → module not linked into the IOC. Fix: add the
   lib (+ its dbd) to the Generic IOC build. (e.g. pvlogging's
   `set_logging_enable`/`set_max_array_length` were 0 matches = not linked.)
2. **Function present but no `pvar_func_<Func>Register`** → linked but never
   wrapped as an iocsh command. Fix: add the iocsh registration in the support
   module C source + `registrar(...)` in its `.dbd`, then rebuild. (e.g.
   `DLS8516Configure` was `T` but had no `...ConfigureRegister`, while its
   sibling `DLS8516Display` did — a copy-paste omission, betrayed by mashed
   `DLS85158516*` symbol names.)
3. **Registrar present but command still not found** → the module `.dbd` isn't
   in the loaded `ioc.dbd` (composition problem). Compare with a sibling
   command that works.

Diff a working sibling against the broken one (`nm "$F" | grep -i 8515` vs
`8516`) to localise which of the three it is.

## ibek st.cmd <-> NFS layout contract

ibek's `st.cmd.jinja` renders fixed paths the crate reads after mounting its
export at `/epics`:

```text
cd "{{ get_env('IOC') }}"                       -> /epics/ioc
dbLoadDatabase dbd/ioc.dbd                       -> /epics/ioc/dbd/ioc.dbd
STREAM_PROTOCOL_PATH /epics/runtime/protocol/
set_requestfile_path("/epics", "runtime")        -> autosave *.req
dbLoadRecords {{ get_env('RUNTIME_DIR') }}/ioc.db
```

`get_env` has **no default** — an unset env var renders empty. So:

- **Foot-gun:** if `RUNTIME_DIR` is unset when ibek runs, `dbLoadRecords`
  becomes `/ioc.db` (wrong). rtems-proxy must pass `RUNTIME_DIR=/epics/runtime`
  to the ibek subprocess (`hybrid.py:_run_ibek_generate`).
- The NFS export must therefore be laid out as **`runtime/`** (st.cmd, ioc.db,
  protocol/, autosave *.req) and **`ioc/dbd/`** — not flat. `_copy_to_nfs`
  builds exactly these two subfolders.
- Autosave `*.req` aggregates (`autosave_settings.req`/`autosave_positions.req`)
  are emitted by ibek into the runtime dir only if a loaded template has a
  matching `<stem>_settings.req`/`_positions.req` under `/epics/support/**`;
  none match -> none emitted (not an error).

When changing the runtime files on a real crate, the NFS export must be
emptied and re-copied (stale flat files — e.g. an old st.cmd pointing at the
retired `/epics_rtems_root` mount — will otherwise be booted).

## ibek substitution foot-gun: shared `.template` -> positional row misalignment

ibek (`render_db.py`) merges **every** `databases:` entry across **all** entities
that points at the **same** `.template` path into **one** msi `pattern { … }`
block. The header is taken from the arg-key order of the **first** entity to
reference that file; every other entity's row values are then appended **in that
entity's own arg order — ibek never re-keys by name**. So if two different
`entity_model`s instantiate the same template with args in different order, the
second's values land in the **wrong columns**, silently.

- **Symptoms (at `dbLoadRecords` of the expanded `ioc.db`):**
  `Can't set "<rec>.<FIELD>" to "<value>": Illegal choice` / `No digits to
  convert` (a string value landed in a menu/numeric field), and garbage record
  names like `4:SEQCCHV` (a delay/number value landed in the `device` column).
- **Diagnose:** regenerate the subst to a scratch dir
  (`ibek runtime generate --no-pvi <ioc.yaml> /epics/ibek-defs/*.yaml -o /tmp/x`;
  exclude a symlinked def and pass a writable copy if you need to edit one),
  then for each `file "…template" {` block compare the `pattern { … }` header to
  the offending rows. A quick check: every value row must have the **same column
  count** as the header (regex `"([^"]*)"` per row); a count mismatch = guaranteed
  break, and equal counts can still be **semantically** swapped (e.g. SELM↔gauge).
- **Fix:** make the wrapper model list that template's args in the **exact** order
  of the owning module's own `entity_model`. When the owning model uses
  `args: { .*: }` (regex = all params), the header is the entity's **full**
  param list **including ibek's injected `type, entity_enabled` prefix** — the
  wrapper must reproduce those two leading (ignored) columns too.

### Companion foot-gun: re-instantiating a group template needs a unique device

A "wrapper" model (e.g. vacuumSpace `space`/`space_b`) that re-instantiates
another module's group template (`mks937aGaugeGroup`, `digitelMpcIonpGroup`,
`dlsPLC_vacValveGroup`, …) must give each group a **unique device**, or the
group's `$(device):PLOG/:P/:STA/…` records collide with the wrapper's own
`space.template` records → `Record "…:PLOG" of type sel redefined with new type
calc` + `dbRecordHead: tempList not empty`. The DLS builder convention
(`vacuumSpace/etc/builder.py::_make_groups`) is `device = $(device):<COMP>G`
(`GAUGEG`/`IONPG`/`IMGG`/`PIRGG`/`VALVEG`), and `space.template`'s
`gauge`/`ionp`/… macros then point at those group devices (`{{ device }}:GAUGEG`)
so the top-level space reads the group's combined output. The builder only makes
a group when ≥2 of a component exist; an ibek model can't express that
conditional, so the pragmatic equivalent is **always** make the group (padding
to 8 with the first device) — collision-free and correct, at the cost of extra
internal `:<COMP>G` PVs for single-device components.

## Generic-IOC top `Makefile` foot-guns (`.../ioc/<gen-ioc>/Makefile`)

The top-level Makefile of a DLS generic IOC (e.g. `bl-va-ioc-01`) generates
`data/msi.vars` and stages StreamDevice protocol files into `data/` for the NFS
export. Three non-obvious traps, all hit June 2026:

- **`data/` is `.gitignore`d** (like `bin/dbd/db/lib`), so a fresh clone lacks
  it. Any recipe that redirects into it (`> data/msi.vars`) dies on a clean
  build with `/bin/sh: data/...: No such file or directory`. Every such target
  must `@mkdir -p $(@D)` (or `mkdir -p data`) as its first recipe line. Latent
  until you build a fresh clone — an old clone where `data/` already exists
  masks it.
- **Top-level `DATA += ...` is DEAD.** EPICS's `DATA`/`buildInstall` install
  mechanism only fires inside **App** dirs, **never at TOP**. A top Makefile that
  does `DATA += $(all_protos)` (protos gathered from `$(SYS_EDM_PATHS)`, i.e.
  every module's `data/*.proto*`) installs **nothing** → `data/` ends up with
  only `msi.vars` → rtems-proxy's `hybrid.py` glob `data/*.proto*` finds nothing
  → the NFS `runtime/protocol/` folder is created but **empty**. Fix: an explicit
  `protocols` target hooked on `all` that copies the protos itself:
  ```makefile
  all: submodules protocols data/msi.vars
  protocols:
  	@mkdir -p data
  	@for f in $(all_protos); do install -m 644 "$$f" data/; done
  ```
  Use `install -m 644`, **not `cp`**: prod-sourced protos are mode `555`
  (read-only), so a second build's `cp` hits `Permission denied: cannot create
  regular file 'data/x.protocol'` trying to overwrite the read-only dest.
  `install` unlinks+recreates and pins a deterministic owner-writable,
  world-readable mode (0644) (what the NFS root-squash export needs; see the
  dbd-perms section).
- **Submodule lazy-init.** `ibek-support` / `ibek-support-dls` are git
  submodules, empty after a fresh clone, and the `configure/CONFIG` build umask
  does NOT reach them. Hook a `submodules` target on `all` that inits **only the
  un-checked-out ones** — a blanket `git submodule update --init` would detach an
  already-populated submodule to its recorded SHA and **orphan local branch
  work** in it:
  ```makefile
  submodules:
  	@git submodule status | awk '/^-/ { print $$2 }' | while read p; do \
  		git submodule update --init --recursive "$$p"; done
  ```
  (`git submodule status` prefixes an un-initialised submodule with `-`.)
  Running inside a build recipe also gives the checkout the build umask (0022) →
  world-traversable, fixing the otherwise-unreachable submodule perms.

## DLS8515/8516 serial: "port connects but device gives No reply"

Distinct from "could not connect" (missing `/dev/ttyNNN` node — see the
`DLS8516Configure` registrar story). `No reply within 1000 ms` from StreamDevice
means the asyn port opened fine but the **line parameters are wrong** (baud,
data bits, parity, stop) so framing is garbled and nothing comes back.

Card → port → module map (this IOC): cards configure as `ty_<card>_<chan>`.
`DLS8515Configure(40,…)`→`ty_40_*`, `(41,…)`→`ty_41_*` are **8515**;
`DLS8516Configure(42,…)`→`ty_42_*` is **8516**. Both `*Configure` funcs call the
same `DLS85158516Configure()` and pre-config every channel to **9600 8N2**
(`drvDLS8515-RTEMS.c`; legacy `drvDLS8515.c` identical) — so the driver default
is NOT what separates a working card from a failing one.

Diagnostic: correlate working vs failing ports against `asynSetOption` lines in
the generated st.cmd (`/ioc_nfs/runtime/st.cmd`). DLS devices commonly run
**7E2** (bits 7, parity Even, stop 2), NOT the driver's 8N2 default — so a
channel that relies on the default talks to a 7E2 device at 8N2 and gets no
reply. Ports with explicit settings in `ioc.yaml` get `asynSetOption` and work;
ports without get the wrong framing and fail.

- **Watch the emit gating:** a channel template may only emit `asynSetOption`
  when `baud:` is present, silently dropping `parity:`/`stop:` set without a
  baud. Diff `ioc.yaml` channel params against the actual `asynSetOption` lines
  in st.cmd — a channel whose `parity: E` never appears in st.cmd is the smoking
  gun. The fix is per-channel serial settings in `ioc.yaml` (recovered from the
  original VxWorks/XmlBuilder build), and/or a template fix to emit asynSetOption
  for parity/stop/bits independent of baud.

- **Mapped-enum vs template mismatch (the parity bug, fixed June 2026):** ibek's
  `ioc_factory.py::fixup_enums` renders an enum param differently depending on
  whether its `values:` are MAPPED. `{E: even, O: odd, N: none}` → the param
  renders as the *value* (`"even"`/`"odd"`/`"none"`); `{E:, O:, N:}` (null
  values) → it renders as the *key* (`"E"`). DLS8515channel.parity is mapped, so
  a template testing `parity == "E"` never matched and **no parity asynSetOption
  was emitted** — every 7E2 gauge ran 7N2, framing errors, "No reply within
  1000 ms". Fix in `DLS8515.ibek.support.yaml`: make both channels' parity enum
  mapped to asyn's literal values and have the template emit
  `asynSetOption(...,"parity","{{parity}}")` gated on `parity != "none"`. Parity
  was the only mapped enum and the only one that broke; baud/data/stop/flow are
  unmapped and their keys are already the literal asyn values (7,2,H,S).

## "findInterface asynInt32Type" on every FINS record — missing FINS port layer

DLS PLC records (`dlsPLC.vacValve`/`read100`/`interlock`/`temperature`, and the
`:ACTUALCON` ao, `:INTn:RESET` ao) use `DTYP=asynInt32` with
`@asyn(PORT, addr, 0) FINS_DM_READ`/`FINS_DM_WRITE`. The `asynInt32` interface
**and** the `FINS_DM_*` drvUser strings are provided by a **FINS device port**
created by `finsDEVInit(finsPort, serialPort)` (after
`HostlinkInterposeInit(serialPort)`) — NOT by the bare serial port. If st.cmd
only has `drvAsynSerialPortConfigure`/`asynSetOption` for `PORT` and no
`HostlinkInterposeInit`/`finsDEVInit`, the port is plain octet-only, so every
FINS record fails at init:

```text
<PV> devAsynInt32::initCommon findInterface asynInt32Type
recGblRecordError: ao: init_record Error (514,11) PV: <PV>
```

These are non-fatal for iocInit (see the "boots but zero PVs" section — they do
not abort `iocBuild`), **but the affected PVs never talk to the PLC**, so it is
a real failure, not noise, when those PVs are the point of the IOC.

Root cause seen June 2026 (bl19i-va-ioc-01): the builder2ibek conversion dropped
the FINS port objects and set each dlsPLC entity's `port:` directly to the
**underlying serial port** (`ty_40_5`/`ty_41_0`/`ty_41_1`/`ty_41_7`). The
instance `ioc.yaml` had **zero** `FINS.FINSHostlink` entities. Confirm in two
greps:

```bash
grep -ni 'FINS\|Hostlink' .../config/ioc.yaml        # broken IOC: NONE
grep -nE 'HostlinkInterposeInit|finsDEVInit' /ioc_nfs/runtime/st.cmd  # NONE
```

A working sibling (bl15i-va-ioc-01.yaml) has one `FINS.FINSHostlink` per serial
port carrying FINS devices, and the dlsPLC entities point at the **FINS** name,
not the serial name:

```yaml
- type: FINS.FINSHostlink
  asyn_port: ty_42_0       # the serial port (asyn.AsynSerial name)
  name: TMPCC1.Hostlink    # the FINS port — MUST be a DISTINCT name
# ...
- type: dlsPLC.read100
  port: TMPCC1.Hostlink    # references the FINS port, NOT ty_42_0
```

`FINS.FINSHostlink` (`FINS.ibek.support.yaml`) emits exactly:
`HostlinkInterposeInit("{{asyn_port}}")` then
`finsDEVInit("{{name}}", "{{asyn_port}}")`. `HostlinkInterposeInit` interposes on
the serial port **in place**; `finsDEVInit` creates a **new** asyn port on top —
hence the FINS name must differ from the serial name (asyn port names are
unique).

Fix (purely an instance `ioc.yaml` change — **no Generic-IOC rebuild**): for each
serial port that carries FINS devices, add a `FINS.FINSHostlink` (distinct
`name`, `asyn_port:` = the serial port) and repoint every dlsPLC `port:` from the
serial name to that FINS name, then regen. The FINS driver is already linked —
`ioc.dbd` has `registrar(finsDEVRegister)` **and**
`registrar(HostlinkInterposeRegister)`, so the iocsh commands exist; they were
just never called.

## Regenerating & deploying the runtime (`msi` must be on PATH)

`rtems-proxy start` runs `ibek runtime generate2` then **`msi`** (EPICS macro
expansion of the .db) then copies `runtime/` + `ioc/` to the NFS export. `msi`
ships with epics-base but is **not on PATH by default** — without it the run
prints `msi: command not found` / `msi expansion failed` and stops before the
NFS copy. It lives at `/epics/epics-base/bin/linux-x86_64/msi`; this repo
symlinks it into `.venv/bin/` (already on PATH) so the subprocess finds it.
If that symlink is missing (e.g. venv rebuilt), recreate it or
`export PATH=/epics/epics-base/bin/linux-x86_64:$PATH` before the run.

Regen + verify a serial/template change (no crate connection needed):

```bash
rtems-proxy start --hybrid --no-connect \
  --instance /workspaces/i19-services/services/bl19i-va-ioc-01
# generate2 writes /epics/runtime/st.cmd; after msi the NFS copy lands at
# /ioc_nfs/runtime/st.cmd (this is the file the crate boots).
grep -n 'asynSetOption\|parity' /ioc_nfs/runtime/st.cmd
```

Note `/epics/ibek-defs/<MODULE>.ibek.support.yaml` is a **symlink** into the
module's `ibek-support-*` tree (e.g.
`/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01/ibek-support-dls/DLS8515/...`), so
editing the module def is picked up by the next regen with no copy step. The
`IOC binary not found ... .boot` message at the end is expected under
`--no-connect` (nothing is built/booted) and does not affect the generated
st.cmd.

## "boots but zero PVs" — a fatal iocInit step aborts before the CA server

`iocInit` runs `iocBuild` → `iocRun`. If any **`iocBuild`** step fails (e.g.
`iocBuild: asInit Failed.`), iocInit returns early and **never reaches
`iocRun`**, so the CA server never starts — the crate prompt still returns but
serves no PVs. When triaging a no-PV log, scan for a `*Build: ... Failed` /
fatal line near `iocInit`; everything above it (asyn `findInterface` failures,
`ao: init_record Error (514,11)`, `save_restore: Can't open file`, unregistered
iocsh commands) is **non-fatal noise** that does not stop PVs on its own.
(Non-fatal ≠ harmless: mass `findInterface asynInt32Type` failures mean a whole
class of PVs is dead — see the FINS port-layer section above.)

- **Foot-gun (pvlogging):** `_copy_to_nfs` stages only `runtime/` and
  `ioc/dbd/` — nothing under `/epics/support/...`. The `pvlogging` module's
  st.cmd line `asSetFilename /epics/support/pvlogging/src/access.acf` then
  points at a file absent from the NFS export, `asInit` fails hard, iocInit
  aborts, no PVs. Fix: **remove pvlogging from the instance `ioc.yaml`** and
  re-gen runtime assets (confirmed fix, June 2026). Any support module that
  needs an absolute `/epics/support/...` file at boot has the same problem —
  the file must be copied into the NFS tree too, or the feature dropped.

## "registerRecordDeviceDriver failed <every recordtype>" — unreadable dbd dir

A boot log where `dbLoadDatabase dbd/ioc.dbd` is immediately followed by
`registerRecordDeviceDriver failed` for *every* recordtype (aSub, ai, ao, bi …)
plus `registryJLinkAdd failed calc` means **pdbbase is empty** — the dbd never
loaded. It is NOT a dbd-content or binary problem:

- `registerRecordDeviceDriver failed X` (base `registryCommon.c`) fires only
  when `dbFindRecordType(pdbbase,"X")` misses *and* `registryRecordTypeAdd`
  already **succeeded** — so the binary's record support is linked fine; the
  recordtype just isn't in pdbbase.
- The real error is one line up, easily missed because it has no newline:
  `filename="…/dbStatic/dbLexRoutines.c" line number=NNN dbRead opening file
  dbd/ioc.dbd`. That is `dbReadCOM` reporting **`dbOpenFile()` returned NULL**
  → `goto cleanup` → nothing parsed. The crate **could not open the file**.

Root cause seen June 2026: the `ioc/dbd/` directory on the NFS export was mode
**0750** (`drwxr-x---`). The crate NFS-mounts the export as a root-squashed /
anonymous user, so it traverses `ioc/` (0755) but is denied entry to `dbd/` —
open fails. `runtime/st.cmd` loads fine precisely because `runtime/` is 0755.
The 0750 came from `_copy_to_nfs` doing `rsync -r` of the build-tree `dbd/`
(which is 0750), and `cp -a` then propagating it to the live export.

**Rule: every directory the crate reads under `/epics` must be world-traversable
(o+rx) and every file world-readable (o+r).** Confirm with
`namei -l /ioc_nfs/ioc/dbd/ioc.dbd` — any dir without world `x` breaks the boot.

- `_copy_to_nfs` now copies dbd with `rsync -r --chmod=D755,F644` plus an
  explicit `chmod 0755` on `ioc/` and `ioc/dbd/` (the explicit chmod is needed
  because with a `src/` trailing slash rsync does NOT re-perm the transfer's
  **top** destination dir, only its contents).
- Manual one-shot repair on the live export:
  `chmod -R a+rX /dls_sw/<bl>/epics/rtems/<ioc>` (capital `X` = add traverse to
  dirs only, never makes data files executable), then reboot.
- The deploy step is `cp -a /ioc_nfs/. /dls_sw/<bl>/epics/rtems/<ioc>/` — `cp -a`
  **preserves** perms, so fixing `/ioc_nfs` then re-deploying carries the fix.
