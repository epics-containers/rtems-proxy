ARG PYTHON_VERSION=3.12

<<<<<<< before updating
##### developer stage ##########################################################
FROM python:${PYTHON_VERSION} as developer

# The build stage installs the context
FROM developer as build
COPY . /context
WORKDIR /context
RUN pip install --user .

# additional python packages
RUN pip install -r requirements.txt

##### runtime stage ############################################################
FROM python:${PYTHON_VERSION}-slim as runtime

COPY --from=compile-image /root/.local /root/.local

# Set up the environment - for native IOCs these are set by the epics-base
# environment stage. Because rtems-proxy does not derive from epics-base
# these are replicated here.
ENV EPICS_TARGET_ARCH=RTEMS-beatnik
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
=======
# Set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH
>>>>>>> after updating
