# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
ARG PYTHON_VERSION=3.12

##### developer stage ##########################################################
FROM python:${PYTHON_VERSION} as developer

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv-proxy
ENV PATH=/venv-proxy/bin:$PATH

# The build stage installs the context into the venv
FROM developer as build
COPY . /context
WORKDIR /context
RUN pip install .

# additional python packages
RUN pip install -r requirements.txt

##### runtime stage ############################################################
FROM python:${PYTHON_VERSION}-slim as runtime

# The runtime stage copies the built venv into a slim runtime container
COPY --from=build /venv-proxy/ /venv-proxy/
ENV PATH=/venv-proxy/bin:$PATH

# Set up the environment - for native IOCs these are set by the epics-base
# environment stage. Because rtems-proxy does not derive from epics-base
# these are replicated here.
ENV TARGET_ARCHITECTURE=RTEMS-beatnik
ENV EPICS_HOST_ARCH=linux-x86_64
ENV EPICS_ROOT=/epics
ENV EPICS_BASE=${EPICS_ROOT}/epics-base
ENV SUPPORT ${EPICS_ROOT}/support
ENV IOC ${EPICS_ROOT}/ioc

# get a few necessary EPICS binaries
ENV bin=/epics/epics-base/bin/linux-x86_64/
ENV lib=/epics/epics-base/lib/linux-x86_64/
COPY --from=ghcr.io/epics-containers/epics-base-runtime:7.0.8ec2b1 \
     ${bin}/caget ${bin}/msi ${bin}/caput ${bin}/camonitor /usr/bin
COPY --from=ghcr.io/epics-containers/epics-base-runtime:7.0.8ec2b1 \
     ${lib}/libca.* ${lib}/libCom.* /usr/lib/

# set up the IOC startup script
COPY proxy-start.sh /proxy-start.sh

ENTRYPOINT ["rtems-proxy"]
CMD ["--version"]
