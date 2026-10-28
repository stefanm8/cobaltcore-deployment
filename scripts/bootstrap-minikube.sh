#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
context=cobaltcore
minikube start -p "$context" --driver=docker --container-runtime=containerd \
  --cpus=4 --memory=8192 --kubernetes-version=v1.34.2 --keep-context
bash "$root/scripts/start-local-source.sh"
kubectl --context="$context" apply --server-side -k "$root/bootstrap/runtime/operator"
kubectl --context="$context" wait crd/fluxinstances.fluxcd.controlplane.io \
  --for=condition=Established --timeout=2m
kubectl --context="$context" apply -k "$root/bootstrap/runtime/instance"
kubectl --context="$context" -n flux-system wait fluxinstance/flux \
  --for=condition=Ready --timeout=10m
kubectl --context="$context" apply -k "$root/bootstrap/flux"
echo 'Flux is reconciling. Run: kubectl --context=cobaltcore -n flux-system get kustomizations -w'
