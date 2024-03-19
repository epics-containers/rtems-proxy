#!/bin/bash

set -x

# This is the folder the PVC for the nfsv2tftp shared volume is mounted into.
export RTEMS_ROOT=${RTEMS_ROOT:-/nfsv2-tftp}

if [ ! -d ${RTEMS_ROOT} ]; then
    echo "ERROR: No PVC folder found."
    # make a folder for testing outside of the cluster
    mkdir -p ${RTEMS_ROOT}
fi

# copy the IOC instance's runtime assets into the shared volume
cp -rL /epics/ioc ${RTEMS_ROOT}
cp -r /epics/runtime ${RTEMS_ROOT}
# move binary to the root for shorter paths
mv ${RTEMS_ROOT}/ioc/bin/*/ioc.boot ${RTEMS_ROOT}
# fix up the paths in st.cmd
sed -i "s|/epics/|/iocs/${IOC_LOCATION}/${IOC_NAME}/|" ${RTEMS_ROOT}/runtime/st.cmd

# keep the container running ...
while true; do
    sleep 2
done
