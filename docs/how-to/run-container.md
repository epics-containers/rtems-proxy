# Run in a container

Pre-built containers with rtems-proxy and its dependencies already
installed are available on [Github Container Registry](https://ghcr.io/epics-containers/rtems-proxy).

## Starting the container

To pull the container from github container registry and run:

```
$ podman run ghcr.io/epics-containers/rtems-proxy:latest --version
```

To get a released version, use a numbered release instead of `latest`.

:::{note}
podman is already installed on DLS workstations. The first time you use it on a
workstation, run the shared setup script:

```bash
/dls_sw/apps/setup-podman/setup.sh
```
:::

In normal use you would not start this container by hand — Kubernetes runs it
from the instance `values.yaml`, or you open it as the devcontainer for local
work. See [](../reference/configuration.md) and
[](./set-up-the-devcontainer.md).
