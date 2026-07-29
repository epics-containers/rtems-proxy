# Why a proxy container

At DLS we are moving to running EPICS IOCs in Kubernetes, and at the same time
transitioning all our VME crates from VxWorks to RTEMS.

Linux soft IOCs run natively as pods. An RTEMS IOC cannot — it runs on a VME
crate, not on a cluster node. `rtems-proxy` is the container that stands in for
it, so that an RTEMS IOC can be managed with the same workflow as a soft IOC.

## What the proxy does

- Uses telnet and pexpect to control the RTEMS IOC running on the VME crate.
- Configures the crate by dropping into motBoot and setting NVM variables.
- Starts and stops the IOC by sending commands to the telnet session.
- Monitors the IOC by connecting the telnet session to the stdio of the
  container.
- Manages the IOC runtime assets:
  - copies the IOC binary to a TFTP server for initial booting of the RTEMS
    target;
  - copies runtime assets (startup script, EPICS database, stream device
    protocol files) to an NFSv2 server for the target to read at runtime.

## What this buys you

Because the proxy presents the same interface as a soft IOC container,
building and managing RTEMS IOCs becomes an almost identical workflow:

- Starting and stopping IOCs is done the same way.
- Building and deploying new versions is done the same way.
- Logging is identical — the stdout of the proxy container provides the logs,
  just as the stdout of a Linux soft IOC container does.
- The proxy is designed to work inside a developer container too, so an RTEMS
  IOC can be debugged and tested locally, again just like a soft IOC.

## Further reading

For the epics-containers approach in general, see the
[epics-containers documentation](https://epics-containers.github.io/). For DLS
specific implementation details see the
[DLS documentation](https://dev-guide.diamond.ac.uk/epics-containers/).
