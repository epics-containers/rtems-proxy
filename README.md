[![CI](https://github.com/epics-containers/rtems-proxy/actions/workflows/ci.yml/badge.svg)](https://github.com/epics-containers/rtems-proxy/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/epics-containers/rtems-proxy/branch/main/graph/badge.svg)](https://codecov.io/gh/epics-containers/rtems-proxy)
[![PyPI](https://img.shields.io/pypi/v/rtems-proxy.svg)](https://pypi.org/project/rtems-proxy)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# rtems_proxy

Support for a K8S proxy container in controlling and monitoring RTEMS EPICS IOCs


Source          | <https://github.com/epics-containers/rtems-proxy>
:---:           | :---:
PyPI            | `pip install rtems-proxy`
Docker          | `docker run ghcr.io/epics-containers/rtems-proxy:latest`
Releases        | <https://github.com/epics-containers/rtems-proxy/releases>

```
rtems_proxy --help
```
## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

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
