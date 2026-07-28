# Update the golden-file test baselines

For why the baselines work this way, see
[](../explanations/golden-file-tests.md).

## Run the hybrid tests

`ibek-support-dls` lives on internal GitLab, so these tests only run where it
is reachable. They skip cleanly elsewhere.

```bash
git submodule update --init        # ibek-support + ibek-support-dls
uv run --group ci pytest tests/test_hybrid.py
```

## The regen → review → redeploy loop

When `builder2ibek` or a submodule is bumped, by you or by Renovate:

1. **Regenerate** the baselines:

   ```bash
   tests/samples/make_samples.sh                        # all IOCs
   tests/samples/make_samples.sh BL19I-VA-IOC-01.xml    # or just one
   ```

2. **Review the diff.** This is where your judgement goes — the test cannot
   know whether a change is desirable, only that it happened.
   - existing IOC unchanged → backward-compat held;
   - changed and intended (an improvement or a necessary fix) → accept and
     commit the new baseline;
   - changed and *not* intended → a regression; fix `ibek-support*` (or hold
     the `builder2ibek` bump) rather than committing the bad baseline.

3. **Redeploy what the diff touched.** The committed baseline tracks what
   `main` now generates; a running IOC is a separate axis. So **the set of
   baselines that changed is your redeploy worklist** — those are the deployed
   IOCs now drifting from the fixed output.

## Add a new real IOC

The workflow this suite is built for: while bringing up a real RTEMS IOC you
make whatever `ibek-support*` changes are needed to get it working on hardware,
then capture that as a regression test.

1. **Merge/release first.** Get the `ibek-support*` changes onto `main` (and
   release `builder2ibek` if you needed a tool fix), then point the submodules
   and the pinned `builder2ibek` at those versions. This is the one piece of
   discipline the model needs: don't bake a baseline from an unmerged branch or
   an unreleased tool, or the pin can't be reproduced.
2. Drop the builder XML into `tests/samples/<IOC-NAME>.xml`.
3. Run `tests/samples/make_samples.sh <IOC-NAME>.xml` to generate its
   baselines.
4. Review the diff — both that the new IOC looks right **and** that no existing
   IOC's baseline moved unexpectedly — then commit XML and baselines together.
