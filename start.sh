#!/bin/bash

set -xe

# This is the folder the PVC for the nfsv2tftp shared volume is mounted into.
# It will be served as /iocs/${IOC_NAME}/files
# over nfsv2 and tftp
#
# Each RTEMS IOC will mount its sub-folder as /epics - meaning that the file
# paths are identical to native x86 EPICS IOCs
export PVC_ROOT=/nfsv2tftp

# start.sh requires these environment variables to be set
export EPICS_ROOT=/epics
export SUPPORT=${EPICS_ROOT}/support
export IOC=${EPICS_ROOT}/ioc

if [ ! -d ${PVC_ROOT} ]; then
    echo "ERROR: No PVC folder found."
    # make a folder for testing outside of the cluster
    mkdir -p ${PVC_ROOT}
fi

# generate the runtime assets
/epics/ioc/start.sh

# copy the runtime assets into the shared volume
cp -r /epics/ioc ${PVC_ROOT}
cp -r /epics/runtime ${PVC_ROOT}
# make the boot file path shorter
ln -s ${PVC_ROOT}/epics/ioc/bin/*/ioc.boot ${PVC_ROOT}

# keep the container running ...
while true; do
    sleep 2
done
