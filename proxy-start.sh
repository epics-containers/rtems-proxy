#!/bin/bash

set -x

# This is the folder the PVC for the nfsv2tftp shared volume is mounted into.
export RTEMS_TFTP_PATH=${RTEMS_TFTP_PATH:-/nfsv2-tftp}

if [ ! -d ${RTEMS_TFTP_PATH} ]; then
    echo "ERROR: No PVC folder found."
    # make a folder for testing outside of the cluster
    mkdir -p ${RTEMS_TFTP_PATH}
fi

# copy the IOC instance's runtime assets into the shared volume
cp -rL /epics/ioc ${RTEMS_TFTP_PATH}
cp -r /epics/runtime ${RTEMS_TFTP_PATH}
# move binary to the root for shorter paths
mv ${RTEMS_TFTP_PATH}/ioc/bin/*/ioc.boot ${RTEMS_TFTP_PATH}
# fix up the paths in st.cmd
sed -i "s|/epics/|/iocs/${IOC_LOCATION}/${IOC_NAME}/|" ${RTEMS_TFTP_PATH}/runtime/st.cmd

# keep the container running ...
while true; do
    sleep 2
done
