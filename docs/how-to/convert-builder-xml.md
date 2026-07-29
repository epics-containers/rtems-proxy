# Convert builder XML to ioc.yaml

Use `builder2ibek` to convert an existing VxWorks XmlBuilder definition into an
ibek instance definition:

```bash
uvx builder2ibek xml2yaml \
    --yaml <services-repo>/services/<ioc-name>/config/ioc.yaml \
    <path-to-builder-xml>
```

For example, for bl19i-va-ioc-01:

```bash
uvx builder2ibek xml2yaml \
    --yaml /workspaces/i19-services/services/bl19i-va-ioc-01/config/ioc.yaml \
    /dls_sw/prod/R3.14.12.7/support/BL19I-BUILDER/25-3-1/etc/makeIocs/BL19I-VA-IOC-01.xml
```

## Known conversion issues

- `builder2ibek` converts `vacuumValve` entities to `dlsPLC`, but misses
  `vacuumValve.vacuumValveReadExtra`. This entity has no `dlsPLC` equivalent yet
  and must be manually commented out of `ioc.yaml`.
- Older `builder2ibek` versions generated zero-indexed fields (`ionp0`,
  `gauge0`) where the support YAMLs expect one-indexed (`ionp1`, `gauge1`).
  Updating `builder2ibek` fixes this.

## Generate the validation schema

`builder2ibek` writes a schema header at the top of the generated `ioc.yaml` —
the path is the default of its `--schema` option:

```yaml
# yaml-language-server: $schema=/epics/ibek-defs/ioc.schema.json
```

That file does not exist until you create it. Generate it from the
`ibek-support` and `ibek-support-dls` submodules of the Generic IOC you are
about to boot, so the schema tracks the same support YAML versions as the
binary:

```bash
export IOC_ORIGINAL_LOCATION=/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01

mkdir -p /epics/ibek-defs
ibek ioc generate-schema --no-ibek-defs \
    --output /epics/ibek-defs/ioc.schema.json \
    $IOC_ORIGINAL_LOCATION/ibek-support/*/*.ibek.support.yaml \
    $IOC_ORIGINAL_LOCATION/ibek-support-dls/*/*.ibek.support.yaml
```

For the beamline vacuum Generic IOC that is 139 support YAMLs and a ~2 MB
schema. Writing it to `/epics/ibek-defs/ioc.schema.json` means the header
`builder2ibek` already wrote lines up, and VS Code validates the file as you
edit it — no further setup.

The definitions must be passed **explicitly** because this runs before any
hybrid run. `generate-schema` otherwise scans `/epics/ibek-defs` for
`*.ibek.support.yaml`, and that symlink farm is only populated by
[step 3 of the pipeline](../reference/hybrid-pipeline.md), so on a fresh
container the bare command fails with:

```text
No `definitions` given and none found in /epics/ibek-defs
```

`--no-ibek-defs` keeps the result deterministic by stopping ibek from also
folding in whatever a previous hybrid run left there. If you have already run
hybrid prepare for this instance, the symlink farm is correct and the bare
`ibek ioc generate-schema --output /epics/ibek-defs/ioc.schema.json` works.

## Validate from the command line

The editor is the normal place to read these errors, and a clean file really
does mean zero schema errors. To check from a terminal instead:

```bash
cd <services-repo>/services/<ioc-name>/config

uvx --with jsonschema --with ruamel.yaml python -c "
import json, jsonschema
from ruamel.yaml import YAML
schema = json.load(open('/epics/ibek-defs/ioc.schema.json'))
doc = YAML(typ='safe').load(open('ioc.yaml'))
validator = jsonschema.validators.validator_for(schema)(schema)
errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
print(f'{len(errors)} errors')
for e in errors:
    print(' ', list(e.path)[:2], str(e.message)[:160])
"
```

```{warning}
Parse with ruamel, not PyYAML. PyYAML implements YAML **1.1**, where an
exponent-form scalar with no decimal point — `spon: 1e-06`, as `builder2ibek`
writes it — resolves to a *string*. The schema asks for a number, so every such
field is reported as a spurious `is not valid under any of the given schemas`.
ruamel (YAML **1.2**) resolves it to a float, which is what ibek and the VS Code
`yaml-language-server` both do. If a CLI check disagrees with the editor,
suspect this first.
```

Each genuine error prints as `['entities', <index>] ... is not valid under any
of the given schemas`, where the index is the position in the `entities` list.
That top-level message is rarely the useful one: `entities` items are a `oneOf`
over one branch per entity type, so the failure is reported against the whole
list. Iterate `e.context` for the sub-errors and read only the branch whose
`properties.type.const` equals the entity's own `type`. Typically it reads
`Additional properties are not allowed (...)` plus a few
`'X' is a required property` lines, meaning `builder2ibek` emitted a different
field set than the current support YAML expects.
