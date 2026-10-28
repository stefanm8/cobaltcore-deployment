# CobaltCore deployment

Environment repository for the local `cobaltcore` minikube profile. Reusable
bases come from the clean `feat/gitops-deployment` branch of the CobaltCore fork,
pinned by commit in `bases/*/kustomization.yaml`.

```
bases/                  pinned references to the fork's reusable bundles
overlays/minikube/       local sizing, storage, endpoint and version settings
clusters/minikube/       Flux dependency graph and readiness gates
bootstrap/runtime/      one-time Flux operator and controller installation
bootstrap/flux/         Git source + root reconciliation
bootstrap/argocd/       alternative Argo CD entry point
scripts/                local controller/source bootstrap helpers
```

Install Docker, minikube, kubectl and Git, commit this repository on `main`, then:

```bash
bash scripts/bootstrap-minikube.sh
kubectl --context=cobaltcore -n flux-system get kustomizations
kubectl --context=cobaltcore -n openstack get controlplane
```

The script bootstraps the controller and its Git source. Flux reconciles the
entire stack, including the OpenBao initialization and database-onboarding Jobs.
Commit changes on `main` to deploy them; an uncommitted working-tree edit has no
effect. The local Git daemon exports only this repository, read-only, on
localhost:19418. Minikube on OrbStack reaches it through `host.minikube.internal`.
If using a different driver, verify that hostname reaches the host first, or
change `bootstrap/source/source.yaml` to an HTTPS/SSH Git remote.

The profile deploys the CobaltCore operators plus a Minimal Keystone/Horizon
ControlPlane. It uses development certificates and stores local OpenBao init
keys in a Kubernetes Secret. It does not provision hypervisors, Ceph, or VMs.
Do not use the development bootstrap Jobs in a production overlay.

Access the local gateway in a separate terminal:

```bash
kubectl --context=cobaltcore -n envoy-gateway-system port-forward \
  service/$(kubectl --context=cobaltcore -n envoy-gateway-system get service \
    -l gateway.envoyproxy.io/owning-gateway-name=openstack-gw -o jsonpath='{.items[0].metadata.name}') \
  8443:443
```

Open <https://horizon.127-0-0-1.nip.io:8443>. The local certificate needs a trust
exception. The Keystone endpoint is
<https://keystone.127-0-0-1.nip.io:8443/v3>. Read the admin password when needed:

```bash
kubectl --context=cobaltcore -n openstack get secret controlplane-keystone-admin-credentials \
  -o jsonpath='{.data.password}' | base64 -d
```

For Argo CD, install `bootstrap/runtime` in the same two stages as the script,
then apply `bootstrap/argocd/application.yaml` to an existing Argo CD instance.
The Application owns the stage declarations; Flux remains the Helm and stage
execution engine. Choose this **instead of** `bootstrap/flux`: never have both
root controllers own the same stage declarations. Adjust `repoURL` and the Flux
GitRepository URL together when moving this repository to a remote host.

Stateful stages intentionally use `prune: false`; deleting the root is not a
stack teardown. A minikube profile deletion destroys its local data. Stop the
local source daemon using the PID in `.local/git-daemon.pid` when finished.
