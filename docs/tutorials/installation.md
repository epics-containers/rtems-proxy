# Installation

:::{note}
You rarely need to install rtems-proxy directly. In production it runs as a
container image started by Kubernetes, and for local work you open this
repository's [devcontainer](../how-to/set-up-the-devcontainer.md), which already
has it on the path along with `ibek` and `msi`. Install it standalone only if
you want the CLI on a workstation.
:::

## Check your version of python

You will need python 3.13 or later. You can check your version of python by
typing into a terminal:

```bash
python3 --version
```

## Create a virtual environment

It is recommended that you install into a “virtual environment” so this
installation will not interfere with any existing Python software:

```bash
python3 -m venv /path/to/venv
source /path/to/venv/bin/activate
```

## Installing the library

You can now use `pip` to install the library and its dependencies:

```bash
python3 -m pip install rtems-proxy
```

If you require a feature that is not currently released you can also install
from github:

```bash
python3 -m pip install git+https://github.com/epics-containers/rtems-proxy.git
```

The library should now be installed and the commandline interface on your path.
You can check the version that has been installed by typing:

```bash
rtems-proxy --version
```
