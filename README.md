[![CI](https://github.com/epics-containers/rtems-proxy/actions/workflows/ci.yml/badge.svg)](https://github.com/epics-containers/rtems-proxy/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/epics-containers/rtems-proxy/branch/main/graph/badge.svg)](https://codecov.io/gh/epics-containers/rtems-proxy)
[![PyPI](https://img.shields.io/pypi/v/rtems-proxy.svg)](https://pypi.org/project/rtems-proxy)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# rtems_proxy

Support for a K8S proxy container in controlling and monitoring RTEMS EPICS IOCs


What            | Where
:---:           | :---:
Source          | <https://github.com/epics-containers/rtems-proxy>
PyPI            | `pip install rtems-proxy`
Podman          | `podman run ghcr.io/epics-containers/rtems-proxy:latest`
Documentation   | <https://epics-containers.github.io/rtems-proxy>
Releases        | <https://github.com/epics-containers/rtems-proxy/releases>

## Documentation

Full documentation is at <https://epics-containers.github.io/rtems-proxy>, including a
[worked example](https://epics-containers.github.io/rtems-proxy/main/tutorials/hybrid-ioc-walkthrough.html)
of converting a VxWorks IOC to a hybrid RTEMS IOC.

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.
On a DLS workstation, get it with `module load uv`. We recommend working
in vscode with the provided devcontainer.

### Running Tests and Type Checking

Use `uv` to run the tox test suite:

```bash
uv run tox -p
```

This will run:
- `tests` - pytest with coverage
- `type-checking` - pyright static type checking
- `pre-commit` - code formatting and linting

To run a specific tox environment:

```bash
uv run tox -e type-checking
uv run tox -e tests
uv run tox -e pre-commit
```

### Installing Dependencies

Install all dependencies including dev dependencies:

```bash
uv sync --group dev
```

<!-- README only content. Anything below this line won't be included in index.md -->

See https://epics-containers.github.io/rtems-proxy for more detailed documentation.
