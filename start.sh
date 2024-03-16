#!/bin/bash

set -xe

# This is the folder the PVC for the nfsv2tftp shared volume is mounted into.
# It will be served as /iocs/${IOC_NAME}/files
# over nfsv2 and tftp
#
# Each RTEMS IOC will mount its sub-folder as /epics - meaning that the file
# paths are identical to native x86 EPICS IOCs
#
# This can be configured via globalenv in the beamline shared helm values.yaml
export RTEMS_ROOT=${RTEMS_ROOT:-/nfsv2tftp}

# epics/ioc/start.sh requires these environment variables to be set
export EPICS_ROOT=/epics
export SUPPORT=${EPICS_ROOT}/support
export IOC=${EPICS_ROOT}/ioc

if [ ! -d ${RTEMS_ROOT} ]; then
    echo "ERROR: No PVC folder found."
    # make a folder for testing outside of the cluster
    mkdir -p ${RTEMS_ROOT}
fi

# generate the runtime assets
/epics/ioc/start.sh

# copy the runtime assets into the shared volume
cp -r /epics/ioc ${RTEMS_ROOT}
cp -r /epics/runtime ${RTEMS_ROOT}
# make the boot file path shorter
ln -s ${RTEMS_ROOT}/epics/ioc/bin/*/ioc.boot ${RTEMS_ROOT}

# keep the container running ...
while true; do
    sleep 2
done
