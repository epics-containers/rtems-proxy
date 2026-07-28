# Run in a container

Pre-built containers with rtems-proxy and its dependencies already
installed are available on [Github Container Registry](https://ghcr.io/epics-containers/rtems-proxy).

## Starting the container

To pull the container from github container registry and run:

```
$ docker run ghcr.io/epics-containers/rtems-proxy:latest --version
```

To get a released version, use a numbered release instead of `latest`.
