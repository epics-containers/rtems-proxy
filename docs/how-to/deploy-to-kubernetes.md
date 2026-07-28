# Deploy a hybrid IOC to Kubernetes

In-cluster, the environment variables are set by the Helm chart from
`values.yaml`, the instance config is mounted into `/epics/ioc/config` by
Kubernetes, and the NFS/TFTP volumes are mounted at `/ioc_nfs` and `/ioc_tftp`.
The `--instance` flag is **not** used — everything comes from the environment
and volume mounts.

See [](../reference/configuration.md) for the `values.yaml` shape that drives
this.

## Deploy

The cluster path is identical to any other beamline service; no extra
rtems-proxy machinery is involved at deploy time.

1. Commit the two new files in the services repo:
   - `services/<ioc-name>/values.yaml`
   - `services/<ioc-name>/config/ioc.yaml`
2. Push the branch.
3. If this is a brand-new instance, argocd does not yet know about it.
   Bootstrap it once from the branch:

   ```bash
   ec deploy <ioc-name> <branch-name>
   ```

   On subsequent updates this manual step is not needed — argocd picks up
   changes to an existing instance automatically.
4. Each push to the feature branch has the existing GitOps pipeline (argocd /
   beamline-chart sync) render the Helm chart and deploy the proxy pod.
5. Verify by tailing the proxy-pod logs — the same progress lines as a local
   run should appear, followed by the motBoot configuration, reboot, and the
   live console.
