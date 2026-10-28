# CobaltCore deployment

Environment repository for the local `cobaltcore` minikube profile. Reusable
bundles come from the clean `feat/gitops-deployment` branch of the CobaltCore fork,
referenced directly by commit in each stage's `kustomization.yaml`.

```
overlays/minikube/       single environment entry point and stage definitions
overlays/minikube/*/     stage resources, settings and direct fork references
bootstrap/runtime/      one-time Flux operator and controller installation
bootstrap/flux/         Git source + root reconciliation
scripts/                controller bootstrap and version-lock helpers
```

`overlays/minikube/kustomization.yaml` assembles the whole environment: Flux's
runtime and source/root configuration, plus `stack.yaml` with the stage
definitions. Flux watches this directory. Each stage builds its own subdirectory
and waits for its declared dependencies; this preserves readiness ordering for
operators, certificates, secrets and databases. There is no separate local base
wrapper layer. The root manages its own Flux configuration after initial bootstrap.

Install Docker, minikube, kubectl and Git, clone this repository, then:

```bash
bash scripts/bootstrap-minikube.sh
kubectl --context=cobaltcore -n flux-system get kustomizations
kubectl --context=cobaltcore -n openstack get controlplane
```

The script bootstraps the controller and its Git source. Flux reconciles the
entire stack, including the OpenBao initialization and database-onboarding Jobs.
Push changes to this repository's `main` branch to deploy them. Flux reads the
public GitHub repository over HTTPS every 30 seconds; local edits and unpushed
commits have no effect. The workstation's Git remote uses SSH for pushes. No
GitHub credentials are required inside the cluster for this public repository.

The profile deploys the CobaltCore operators plus a Minimal Keystone/Horizon
ControlPlane. It uses development certificates and stores local OpenBao init
keys in a Kubernetes Secret. It does not provision hypervisors, Ceph, or VMs.
Do not use the development bootstrap Jobs in a production overlay.

This repository owns the ControlPlane instance, Envoy Gateway and its CRDs,
public certificates, Horizon secret mapping, OpenBao bootstrap/unseal Jobs and
database onboarding. Their manifests live under `overlays/minikube/`. The fork
provides reusable operator/infrastructure bases and canonical bootstrap scripts
and policies; all cluster assumptions remain here. The OpenBao bootstrap targets
`shared-services/openbao-0` and tenant `openstack/controlplane`, and its CronJob
unseals the local server after restarts using Kubernetes-custodied init keys.

Chart versions and operator image digests live in each overlay's `versions.yaml`;
service image digests live in the ControlPlane patch. To upgrade, edit these pins
and the fork commit references under `overlays/minikube/`, render the affected stages with
`kustomize build`, then commit. Helm drift detection restores changes made outside
Git. The optional `scripts/lock-versions.py` records versions from a healthy local
installation; install its Python dependency from `scripts/requirements.txt` in a
virtual environment before running it.

## Testing a fork commit

Push the changes to `stefanm8/cobaltcore` on `feat/gitops-deployment`. Copy the full
commit SHA from that branch, then update the direct fork references from this
deployment repository's root (requires Python 3 and Kustomize):

```bash
git ls-remote git@github.com:stefanm8/cobaltcore.git refs/heads/feat/gitops-deployment
export FORK_SHA=FULL_COMMIT_SHA
python3 - <<'PY'
import os, pathlib, re
sha = os.environ['FORK_SHA']
assert re.fullmatch(r'[0-9a-f]{40}', sha), 'Use a full commit SHA'
for path in pathlib.Path('overlays/minikube').rglob('kustomization.yaml'):
    path.write_text(re.sub(
        r'(https://github.com/stefanm8/cobaltcore//[^\s?]+\?ref=)[0-9a-f]{40}',
        lambda match: match[1] + sha, path.read_text()))
PY
(
  set -e
  kustomize build overlays/minikube > /dev/null
  for overlay in overlays/minikube/*; do
    [ -d "$overlay" ] || continue
    kustomize build "$overlay" > /dev/null
  done
)
git diff -- overlays/minikube
```

After every overlay renders successfully, commit the reviewed pin changes and
push `main`. Watch the GitRepository and Kustomizations until their applied
revision matches the **deployment** commit, then check the ControlPlane:

```bash
kubectl --context=cobaltcore -n flux-system get gitrepositories,kustomizations
kubectl --context=cobaltcore get helmreleases -A
kubectl --context=cobaltcore -n openstack get controlplane
```

This tests manifests from the fork commit. Operator or application code changes
also require publishing their images/charts and updating the overlay's image
digests/chart versions. Validate Keystone authentication and Horizon after those
changes. Revert the deployment pin/version commit and push to restore the prior
configuration; application/data migrations may need their own rollback procedure.

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

Stateful stages intentionally use `prune: false`; deleting the root is not a
stack teardown. A minikube profile deletion destroys its local data.
