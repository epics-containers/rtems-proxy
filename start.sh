#!/bin/bash

export PVC_ROOT=/nfsv2tftp

# make a directory structure that matches what the RTEMS crate will mount
# but is really our PVC shared with the nfsv2tftp service
IOC_FOLDER=/iocs/${IOC_NAME}
mkdir /iocs/
ln -s ${PVC_ROOT} ${IOC_FOLDER}

# point ibek at the root IOC folder - all assets will go in the same folder
export IOC=${IOC_FOLDER}
export RUNTIME_DIR=${IOC_FOLDER}
# generate the startup script and subst file
ibek runtime generate /epics/ioc/config/ioc.yaml /epics/ibek-defs/*.support.ibek.yaml
# expand the subst file into a database
includes=$(for i in /epics/support/*/db; do echo -n "-I $i "; done)
msi ${includes} -I${RUNTIME_DIR} -S ${RUNTIME_DIR}/ioc.subst -o ${RUNTIME_DIR}/ioc.db

cp -r /epics/ioc/dbd ${IOC_FOLDER}

# keep the container running ...
while true; do
    sleep 2
done
