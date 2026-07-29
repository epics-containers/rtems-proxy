# Configuration

In a cluster these values come from the Helm chart, rendered from
`values.yaml`. In a devcontainer the `--instance` flag reads the same
`values.yaml` files directly, so the two environments stay in step.

## Beamline-wide globals

Settings shared across all IOCs on a beamline go in
`<services-repo>/services/values.yaml`:

```yaml
global:
  # beamline or accelerator technical area
  domain: i19
  env:
    # default gateway written into the crate's motBoot NVM at configure time
    - name: RTEMS_IOC_GATEWAY
      value: 172.23.119.254
    # subnet mask written into motBoot NVM
    - name: RTEMS_IOC_NETMASK
      value: 255.255.255.0
    # NFS server the crate mounts /ioc_nfs from at boot
    - name: RTEMS_NFS_IP
      value: 172.23.119.226
    # TFTP server the crate fetches its .boot image from
    - name: RTEMS_TFTP_IP
      value: 172.23.119.226
```

## Instance settings

The instance values live at
`<services-repo>/services/<ioc-name>/values.yaml`:

```yaml
ioc-instance:
  # proxy + ibek + msi runtime image (epics-containers registry)
  image: ghcr.io/epics-containers/rtems-proxy-developer:2.1.0
  args:
    # container command: hybrid-mode rtems-proxy wrapped in stdio-socket
    - |
      stdio-socket --ptty "rtems-proxy start --hybrid"

  env:
    # generic IOC build tree — source of ibek-support YAMLs, msi.vars and the .boot binary
    - name: IOC_ORIGINAL_LOCATION
      value: /dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01
    # static IP the crate is given via BOOTP/DHCP by MAC address
    - name: RTEMS_IOC_IP
      value: 172.23.119.98
    # terminal-server host:port for the crate's serial console (telnet)
    - name: RTEMS_CONSOLE
      value: BL19I-NT-TSERV-01:7002

  volumeMounts:
    # rtems-proxy writes runtime assets here; crate mounts the same dir via NFSv2
    - name: nfsv2
      mountPath: /ioc_nfs
      # one subdir per IOC under the shared beamline NFS export
      subPathExpr: $(IOC_NAME)
    # rtems-proxy drops the .boot binary here; TFTP server publishes it to the crate
    - name: tftp
      mountPath: /ioc_tftp
      subPathExpr: $(IOC_NAME)
    # read-only DLS work area — needed to read the generic IOC tree
    - name: work
      mountPath: /dls_sw/work
      readOnly: true
    # read-only DLS prod area — msi reads support-module DB templates from here
    - name: prod
      mountPath: /dls_sw/prod
      readOnly: true

  volumes:
    - name: nfsv2
      hostPath:
        # beamline NFS export root for RTEMS IOCs
        path: /dls_sw/<beamline>/epics/rtems
    - name: tftp
      persistentVolumeClaim:
        # shared PVC backing the beamline TFTP server
        claimName: <beamline>-binaries-claim
    - name: work
      hostPath:
        path: /dls_sw/work
    - name: prod
      hostPath:
        path: /dls_sw/prod
```

## Environment variables

| Variable | Source | Meaning |
| --- | --- | --- |
| `IOC_ORIGINAL_LOCATION` | instance env | Generic IOC build tree — `ibek-support*`, `data/msi.vars`, `bin/RTEMS-beatnik/ioc.boot` |
| `IOC_NAME` | derived | Instance name; with `--instance` it is the services folder name, unchanged |
| `RTEMS_IOC_IP` | instance env | Static IP of the crate |
| `RTEMS_CONSOLE` | instance env | `host:port` of the terminal server for the crate's serial console |
| `RTEMS_IOC_GATEWAY` | global env | Gateway written into motBoot NVM |
| `RTEMS_IOC_NETMASK` | global env | Netmask written into motBoot NVM |
| `RTEMS_NFS_IP` | global env | NFS server the crate mounts at boot |
| `RTEMS_TFTP_IP` | global env | TFTP server the crate fetches its boot image from |
| `EPICS_ROOT` | optional | Root of the EPICS tree, default `/epics` |
| `IBEK_DEFS_PATH` | optional | ibek support YAML symlink farm, default `$EPICS_ROOT/ibek-defs` |
| `IOC_CONFIG_PATH` | optional | Folder holding `ioc.yaml`, default `$EPICS_ROOT/ioc/config` |

The defaults are defined in `src/rtems_proxy/globals.py`.

## What the instance flag does

`--instance <path>` is for local testing, and is **not** used in a cluster. It:

- reads global env vars from `<instance>/../values.yaml`;
- reads instance env vars from `<instance>/values.yaml`;
- derives `IOC_NAME` from the instance folder name;
- sets `IOC_DOMAIN` from `global.domain`;
- symlinks `<instance>/config/` into `/epics/ioc/config` — only when combined
  with `--hybrid`, as this is done by `hybrid_prepare()`.

In a cluster all of this comes from the Helm-rendered environment and
Kubernetes volume mounts instead, so the container command is simply:

```yaml
args:
  - |
    stdio-socket --ptty "rtems-proxy start --hybrid"
```
