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

```
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

- **Foot-gun (pvlogging):** `_copy_to_nfs` stages only `runtime/` and
  `ioc/dbd/` — nothing under `/epics/support/...`. The `pvlogging` module's
  st.cmd line `asSetFilename /epics/support/pvlogging/src/access.acf` then
  points at a file absent from the NFS export, `asInit` fails hard, iocInit
  aborts, no PVs. Fix: **remove pvlogging from the instance `ioc.yaml`** and
  re-gen runtime assets (confirmed fix, June 2026). Any support module that
  needs an absolute `/epics/support/...` file at boot has the same problem —
  the file must be copied into the NFS tree too, or the feature dropped.
