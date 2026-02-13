# RTEMS Hybrid IOCs

This page describes an approach that will be the quickest way to convert existing VxWorks XmlBuilder IOCs to RTEMS.

# Overview

This method will use a Generic IOC shared between all beamlines for each class of IOC. So for example there will be one Generic IOC for Beamline Vacuum which includes the support modules for all beamline vacuum equipment.

1. We will build a Generic RTEMS5 IOC. This will be maintained in https://gitlab.diamond.ac.uk/controls/ioc/BL as a native EPICS 7, RTEMS5 IOC and be released to prod.
   - see [confluence](https://confluence.diamond.ac.uk/x/_w6WFQ)
2. This generic IOC will have a couple of special additions:
   - it will have submodules ibek-support and ibek-support-dls so that we can track versions of the ibek support yaml with versions of the RTEMS IOC.
   - it will have a modified src/Makefile that will collect all stream device protocol files into the `data` folder, for easy protocol file path management (as ibek uses inside fully containerised IOCs)
3. The ioc instance in the services repository will have:
   - mounts of dls_sw/prod and work
   - a reference to the generic IOC in its values.yaml
   - an ioc.yaml converted from an existing vxWorks builder XML file
4. At runtime the startup script will:-
   - use ioc.yaml to get ibek to generate the startup script and database files
     - note that this must use the configure/RELEASE of the generic IOC so that it can make a good search path for `msi` to discovert the correct DB templates
   - place the startup script, database files and protocol files in the correct locations for the IOC to find them (NFSv2 share)
   - place the binary from the generic IOC in the correct location for the IOC to find it (TFTP share)
   - start the IOC using the standard rtems-proxy approach

# Testing

To test the correct operation of the rtems proxy you can do this:

- launch the devcontainer for rtems-proxy and then do one of the following:

## Step 1 initial setup

- Point at a built generic IOC that you have copied to a peer folder and set the IOC_NAME.

```bash
export IOC_NAME=BL06I-MO-IOC-02
export IOC_ORIGINAL_LOCATION=/dls_sw/prod/R7.0.7/ioc/BL06I/BL06I-MO-IOC-02/8-2
```

## Option 1: Run Generic IOC directly without ibek

```bash
rtems-proxy start --no-connect
```

if this works then you should have your runtime assets in the correct places i.e.

This command:
```bash
ls /ioc_*
```

Should show:
```bash
/ioc_nfs:
data  db  dbd  st.cmd  stBL06I-MO-IOC-02.boot

/ioc_nfsv2:

/ioc_tftp:
rtems.ioc.bin
```

# Option 2: Run Generic IOC with ibek

Here we need an ioc.yaml file to generate the startup script and database files.

- pick an ibek IOC to use and run ibek runtime generate to create all the runtime assets in `/epics/runtime`
- generate the runtime assets with ibek
- TODO: work out how to make a epics_db_path for msi


```bash
ibek dev instance /workspaces/i04-services/services/bl04i-va-ioc-01
ibek runtime generate --no-pvi /epics/ioc/config/ioc.yaml ibek-support**/*/*.ibek.support.yaml
includes= somehow we need to work -Ixxx/db -I/xxy/db etc. OR USE an env var if msi supports that
msi -o${RUNTIME_DIR}/ioc.db ${includes} -I${RUNTIME_DIR} -S${RUNTIME_DIR}/ioc.subst
cp ${RUNTIME_DIR}/ioc.db /ioc_nfs/
# also need req files and protocol files?
rtems-proxy start --no-connect
```
