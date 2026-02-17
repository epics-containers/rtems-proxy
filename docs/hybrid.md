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

- launch the devcontainer for rtems-proxy and then try the following:

## Step 1 initial setup

- Point at a built generic IOC set the IOC_NAME.

```bash
export IOC_NAME=BL06I-VA-IOC-01
export IOC_ORIGINAL_LOCATION=/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01
```

## Step 2: Run Generic IOC directly without ibek

This is initial verification that the above settings from Step 1 are correct.

Optionally, clean up the previous state of the target folders:

```bash
rm -rf /ioc_nfs/* /ioc_tftp/*
```

Then start the proxy without connecting to the target:

```bash
rtems-proxy start --no-connect
```

If this works then it will get no errors and copy your runtime assets in the correct places. Verify with:

This command:
```bash
ls /ioc_*
```

Should show:
```bash
/ioc_nfs:
data  db  dbd  st.cmd  stBL06I-VA-IOC-01.boot

/ioc_nfs/data:
BL06I_0.req  BL06I_1.req  BL06I_2.req

/ioc_nfs/db:
BL06I-VA-IOC-01.db

/ioc_nfs/dbd:
BL06I-VA-IOC-01.dbd

/ioc_tftp:
rtems.ioc.bin
```

# Step 3: Generate an ioc.yaml

In this example we will generate a temporary ioc.yaml from the i04 vacuum IOC builder XML file.

In a real example you would add the resulting `ioc.yaml` into your IOC instance definition in the target beamline's services repository.

e.g.
```bash
uvx builder2ibek xml2yaml /dls_sw/work/R3.14.12.7/support/BL19I-BUILDER/etc/makeIocs/BL19I-VA-IOC-01.xml --yaml /workspaces/i19-services/services/bl19i-va-ioc-01/config/ioc.yaml
```

Take a look at the generated `ioc.yaml` and check that it looks correct. It should have a list of support yaml files that are needed to generate the database files for this IOC.

```bash
less /workspaces/i19-services/bl19i-va-ioc-01config/ioc.yaml
```

# Step 4: Run Generic IOC with ibek

Here we will:

- pass the ioc.yaml file to generate the startup script and database files
- we will then make a db lookup path for `msi` to find the correct DB templates
- run msi over the substitution file that ibek generated (https://epics.anl.gov/EpicsDocumentation/ExtensionsManuals/msi/msi.html)
- copy all the runtime files to the NFSv2 share (TFTP for the binary)
  - ibek generated files in `/epics/runtime`)
  - binary from the generic IOC bin folder
  - protocol files and req files (TODO: how do we get these)
- start the IOC with rtems-proxy.


```bash
# for the devcontainer this command links the config folder to /epics/ioc/config
ibek dev instance /workspaces/i19-services/services/bl19i-va-ioc-01
# expand the ioc.yaml into st.cmd and ioc.subst
ibek runtime generate --no-pvi /epics/ioc/config/ioc.yaml $IOC_ORIGINAL_LOCATION/ibek-support**/*/*.ibek.support.yaml
rsync -r $IOC_ORIGINAL_LOCATION/data/ /ioc_nfs/

includes=$(cat $IOC_ORIGINAL_LOCATION/data/msi.args)
msi -o${RUNTIME_DIR}/ioc.db ${includes} -I${RUNTIME_DIR} -S${RUNTIME_DIR}/ioc.subst
rsync ${RUNTIME_DIR}/ioc.db /ioc_nfs/
# also need req files and protocol files?
rtems-proxy start --no-connect
```
