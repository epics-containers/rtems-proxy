# RTEMS Hybrid IOCs

This page describes an approach that will be the quickest way to convert existing VxWorks XmlBuilder IOCs to RTEMS.

This method will use a Generic IOC shared between all beamlines for each class of IOC. So for example there will be one Generic IOC for Beamline Vacuum which includes the support modules for all beamline vacuum equipment.

1. We will build a Generic RTEMS5 IOC. This will be maintained in https://gitlab.diamond.ac.uk/controls/ioc/BL as a native EPICS 7, RTEMS5 IOC and be released to prod.
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
