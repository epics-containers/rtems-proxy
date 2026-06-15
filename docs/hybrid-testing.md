# Testing hybrid mode — the golden-file model

The hybrid end-to-end tests (`tests/test_hybrid.py`) check that the whole
conversion-and-generation pipeline still produces the runtime assets a real
RTEMS crate expects. They follow the **golden-file** pattern (also called
*approval testing* or *characterization testing*): the committed output is the
"last reviewed" result, and the test simply re-runs the pipeline and compares.

See [hybrid.md](hybrid.md) for what the pipeline itself does; this page is about
how it is tested and, more importantly, the workflow for keeping the tests
honest as `ibek-support*` and `builder2ibek` move forward.

## What the test does

For each sample IOC (one builder XML per real IOC, in `tests/samples/`):

```text
builder XML
  --(builder2ibek xml2yaml)-->          ioc.yaml
  --(ibek runtime generate2)-->         st.cmd + ioc.subst   <-- COMPARED
  --(msi, STUBBED)-->                   ioc.db
  --(ibek runtime generate-autosave)--> autosave_*.req
  --(rsync)-->                          /ioc_nfs, /ioc_tftp   <-- placement
```

- **`st.cmd` and `ioc.subst` are the golden files.** They are the genuinely
  validated artifacts: everything ibek decides about how the IOC boots and what
  records it loads is in those two files. The committed baselines live next to
  the XML as `tests/samples/<ioc-name>.st.cmd` and `.ioc.subst`.
- **`msi`, the protocol files, the `dbd/` and the boot binary are stubbed.**
  Expanding `ioc.subst` into `ioc.db` needs support-module db templates that
  only exist under `/dls_sw`, and there is no cross-compiled `.boot` binary in
  CI. So `msi` is replaced by a stub (`conftest.fake_msi_bin`) and the
  `dbd`/proto/binary inputs are stub files (`conftest.build_tree`). For those we
  assert only **placement** — that the pipeline puts them where the crate's
  `st.cmd` expects (`/ioc_nfs/runtime/`, `/ioc_nfs/ioc/dbd/`, `/ioc_tftp/`).
- A volatile absolute path (`dbLoadRecords <RUNTIME_DIR>/ioc.db`) is
  canonicalised to `/epics/runtime` in both the baseline and the comparison, so
  baselines are environment-independent.

## The golden-file model in one paragraph

The baseline is **not a frozen contract — it is the last output you looked at
and approved.** A test failure does not mean the new output is *wrong*; it means
the output *changed* and a human needs to decide whether the change is good. The
test catches **change, not wrongness.** When you are happy with a diff you
regenerate the baselines and commit them; the new files become the new "approved
truth".

Good background reading:

- *Approval testing* — <https://approvaltests.com> (Emily Bache has several
  clear talks and articles on the workflow).
- *Golden files* — popularised in the Go community by Mitchell Hashimoto's
  "Advanced Testing with Go" talk.
- *Characterization tests* — Michael Feathers, *Working Effectively with Legacy
  Code* (the same idea, aimed at pinning down existing behaviour before you
  change it).

## Why the dependencies are pinned, and how they move forward

The output depends on three moving things: `builder2ibek`, `ibek-support` and
`ibek-support-dls`. Golden-file comparison only works against a **stable**
upstream — otherwise every unrelated push elsewhere turns CI red. So all three
are pinned, and bumped deliberately:

- **`ibek-support` and `ibek-support-dls` are git submodules** at the repo root,
  pinned to a reviewed commit. `ibek runtime generate2` reads the entity/schema
  definitions from them (this is *our* pipeline's dependency — note the
  installed `builder2ibek` does **not** read them). They are configured to track
  `main` so Renovate's `git-submodules` manager opens a PR each time `main`
  advances, runs these tests on the bump, and gives you a reviewable diff.
- **`builder2ibek` is pinned in a non-default `ci` dependency group** (see
  `[dependency-groups]` in `pyproject.toml`), not `uvx builder2ibek`. Pinning
  means a new release arrives as a Renovate PR that *runs these tests* — so an
  incompatible change is caught and **attributed to a specific version bump**,
  instead of silently turning CI red with nothing to point at.

### Where the hybrid tests run

`ibek-support-dls` lives on internal GitLab, and `builder2ibek` is currently
pinned to a git commit (uv clones a git source *with its submodules*, and
builder2ibek itself vendors `ibek-support-dls`). Neither can be fetched from a
public GitHub runner. So the hybrid tests are designed to run on a
**DLS-internal runner / devcontainer** and to **skip cleanly elsewhere**:

- they are gated by `requires_dls` (is `ibek-support-dls` checked out?) and
  `requires_builder2ibek` (is `builder2ibek` installed?);
- the default `tox -e tests` env does **not** install the `ci` group, so on
  public CI the hybrid tests skip and only `test_cli`/`test_globals` run;
- to actually run them (where GitLab is reachable):

  ```bash
  git submodule update --init        # ibek-support + ibek-support-dls
  uv run --group ci pytest tests/test_hybrid.py
  ```

Once `builder2ibek` is released to PyPI the git pin becomes a version pin;
wheels carry no submodules, so at that point the only thing keeping the tests
internal is `ibek-support-dls` itself.

### The contract: forward-moving and backward-compatible

The intent is that `ibek-support*` (and `builder2ibek`) **always move forward
and stay backward-compatible.** If that holds, a single pin to the latest `main`
serves every sample IOC, and **the baselines are what enforce the contract**:
regenerating from a newer `main` and diffing is exactly the check "did moving
forward change an existing IOC?".

Backward-compat can legitimately be *stretched*: a real bug fix in `st.cmd`
generation may have to change every existing IOC. That is fine — it is no
different from any golden-file suite. You regenerate, you read the diff, and if
you are happy you commit it.

## The regen → review → redeploy loop

When `builder2ibek` or a submodule is bumped (by you or by Renovate):

1. **Regenerate** the baselines:

   ```bash
   tests/samples/make_samples.sh          # all IOCs
   tests/samples/make_samples.sh BL19I-VA-IOC-01.xml   # or just one
   ```

2. **Review the diff.** This is where your judgement goes — the test cannot know
   whether a change is desirable, only that it happened.
   - existing IOC unchanged → backward-compat held ✅
   - changed and intended (an improvement or a necessary fix) → accept and commit
     the new baseline
   - changed and *not* intended → a regression; fix `ibek-support*` (or hold the
     `builder2ibek` bump) rather than committing the bad baseline

3. **Redeploy what the diff touched.** The committed baseline tracks *what `main`
   now generates*; a running IOC is a separate axis. So **the set of baselines
   that changed is your redeploy worklist** — those are the deployed IOCs now
   drifting from the fixed output, and redeploying them makes reality catch up.

A useful side effect: because a blanket change lights up *every* baseline (and
implies redeploying *every* IOC), the diff size makes the cost visible and nudges
you toward making changes opt-in/parameterised when they can be, rather than
globally flipping behaviour.

## Adding a new real IOC

The workflow this suite is built for: while bringing up a real RTEMS IOC you
make whatever `ibek-support*` changes are needed to get it working on hardware,
then capture that as a regression test here.

1. **Merge/release first.** Get the `ibek-support*` changes onto `main` (and
   release `builder2ibek` if you needed a tool fix), then point the submodules /
   the pinned `builder2ibek` at those versions. This is the one piece of
   discipline the model needs: don't bake a baseline from an unmerged branch or
   an unreleased tool, or the pin can't be reproduced.
2. Drop the builder XML into `tests/samples/<IOC-NAME>.xml`.
3. Run `tests/samples/make_samples.sh <IOC-NAME>.xml` to generate its baselines.
4. Review the diff — both that the new IOC looks right **and** that no existing
   IOC's baseline moved unexpectedly — then commit XML + baselines together.
