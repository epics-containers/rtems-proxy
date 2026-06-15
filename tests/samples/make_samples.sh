#!/usr/bin/env bash
#
# Regenerate the committed baselines for the hybrid end-to-end tests.
#
# For each sample builder XML this:
#   1. converts XML -> ioc.yaml      (builder2ibek xml2yaml)
#   2. generates st.cmd + ioc.subst  (rtems-proxy hybrid: ibek runtime generate2
#      against the ibek-support / ibek-support-dls submodules)
#
# These two files are the genuinely-validated artifacts of hybrid mode. The
# later msi -> ioc.db step needs support-module db templates that only exist
# under /dls_sw, so it is NOT reproduced here (and is stubbed in the tests).
#
# The baselines therefore track the exact submodule SHAs checked out at the
# repo root. After a Renovate git-submodule bump, re-run this and review the
# diff before committing.
#
# Usage:  tests/samples/make_samples.sh [IOC-NAME.xml ...]
# caution: review the diffs before committing.

set -e
THIS=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$THIS/../.." && pwd)
cd "$THIS"

XMLS=${*:-$(ls ./*.xml)}

for xml in ${XMLS}; do
  xml=$(basename "$xml")
  stem=$(echo "${xml%.xml}" | tr '[:upper:]' '[:lower:]')
  echo "=== $xml ==="

  workdir=$(mktemp -d)
  export EPICS_ROOT="$workdir/epics"
  export IOC_ORIGINAL_LOCATION="$workdir/build"
  mkdir -p "$EPICS_ROOT/ioc/config" "$IOC_ORIGINAL_LOCATION"
  # the hybrid pipeline globs ibek-support*/ under IOC_ORIGINAL_LOCATION
  ln -s "$REPO_ROOT/ibek-support" "$IOC_ORIGINAL_LOCATION/ibek-support"
  ln -s "$REPO_ROOT/ibek-support-dls" "$IOC_ORIGINAL_LOCATION/ibek-support-dls"

  echo "  xml2yaml -> ioc.yaml"
  builder2ibek xml2yaml "$THIS/$xml" --yaml "$EPICS_ROOT/ioc/config/ioc.yaml"

  echo "  generate2 -> ${stem}.st.cmd, ${stem}.ioc.subst"
  python - <<'PY'
from rtems_proxy.globals import reload_globals
reload_globals()
from rtems_proxy import hybrid
hybrid._link_ibek_support_yamls()
hybrid._run_ibek_generate()
PY

  # ibek bakes the absolute RUNTIME_DIR into st.cmd (dbLoadRecords ...); rewrite
  # the temp EPICS_ROOT to the canonical /epics the crate actually mounts, so
  # baselines are environment-independent. Also strip ibek's trailing blank line
  # so end-of-file-fixer is happy.
  for f in st.cmd ioc.subst; do
    printf '%s\n' "$(sed "s|$EPICS_ROOT|/epics|g" "$EPICS_ROOT/runtime/$f")" \
      > "$THIS/${stem}.${f}"
  done

  rm -rf "$workdir"
done

echo "done -- review the diffs before committing"
