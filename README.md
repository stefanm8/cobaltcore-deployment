# CobaltCore deployment with Flux

An example of deploying [CobaltCore from the stefanm8 fork](https://github.com/stefanm8/cobaltcore/tree/feat/gitops-deployment)
using Flux instead of `make deploy-infra`. The current environment runs on
minikube and deploys the operators plus a Keystone and Horizon control plane.

The fork provides reusable, cluster-independent bundles. This repository selects
those bundles and supplies the environment's storage, networking, secrets and
sizing. References are pinned to a fork commit so deployments are reproducible.

There is one environment entry point: `overlays/minikube/kustomization.yaml`.
It includes the Flux configuration and the stages in `stack.yaml`. Each stage
references the fork directly or defines an environment resource. The stages
preserve readiness ordering: operators before certificates, OpenBao before
secrets, and database onboarding before the control plane is considered ready.

## Deploy

With Docker, minikube, kubectl and Git installed, clone this repository and run:

```bash
bash scripts/bootstrap-minikube.sh
```

This bootstraps Flux once. Flux then reads this repository's `main` branch from
GitHub and deploys the environment. After that, commit and push configuration
changes to `main`; Flux applies them and corrects drift. Local edits and unpushed
commits do not affect the cluster.

## Observe

Open the included Flux dashboard with a local port-forward:

```bash
kubectl --context=cobaltcore -n flux-system port-forward service/flux-operator 9080:9080
```

Visit [Flux UI](http://localhost:9080). Sources show the fetched Git revision;
Kustomizations and Helm releases show reconciliation and health. `Ready` means
their configured checks passed; `Reconciling` means work is in progress. Open a
resource to inspect its revision, conditions and events.

```bash
kubectl --context=cobaltcore -n flux-system get gitrepositories,kustomizations
kubectl --context=cobaltcore get helmreleases -A
kubectl --context=cobaltcore -n openstack get controlplane
```

This is a development example with local certificates and OpenBao bootstrap keys
stored in Kubernetes. It does not provision hypervisors, Ceph or VMs. Stateful
stages retain data when removed from Git; deleting the minikube profile destroys
that profile's data.
