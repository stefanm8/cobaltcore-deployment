#!/usr/bin/env python3
"""Record the successfully installed chart versions in each minikube overlay.

Requires Python with PyYAML, kubectl, and the cobaltcore context. No cluster writes.
"""
import json
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
releases = json.loads(subprocess.check_output([
    'kubectl', '--context=cobaltcore', 'get', 'helmreleases', '-A', '-o', 'json'
]))['items']
required = {'openbao', 'c5c3-operator', 'envoy-gateway'}
assert required <= {r['metadata']['name'] for r in releases}, 'Wait for all stack stages to install'
assert all(any(c['type'] == 'Ready' and c['status'] == 'True' and c.get('observedGeneration') == r['metadata']['generation'] for c in r.get('status', {}).get('conditions', [])) for r in releases), 'Wait for every HelmRelease to be Ready at its current generation'
patches = {s: [] for s in ['operators', 'openbao', 'controlplane-operator', 'gateway']}
for r in releases:
    name = r['metadata']['name']
    stage = {'openbao': 'openbao', 'c5c3-operator': 'controlplane-operator', 'envoy-gateway': 'gateway'}.get(name, 'operators')
    spec = {}
    if 'chart' in r['spec']:
        spec['chart'] = {'spec': {'version': r['status']['history'][0]['chartVersion']}}
    digest = r['spec'].get('values', {}).get('image', {}).get('digest')
    if digest:
        spec['values'] = {'image': {'digest': digest}}
    if spec:
        patches[stage].append({'apiVersion': r['apiVersion'], 'kind': r['kind'], 'metadata': {'name': name, 'namespace': r['metadata']['namespace']}, 'spec': spec})
for stage, values in patches.items():
    folder = ROOT / 'overlays/minikube' / stage
    (folder / 'versions.yaml').write_text(yaml.safe_dump_all(values, sort_keys=False))
    file = folder / 'kustomization.yaml'
    config = yaml.safe_load(file.read_text())
    kept = []
    for entry in config.get('patches', []):
        if entry.get('path') == 'versions.yaml':
            continue
        body = yaml.safe_load(entry.get('patch', '{}'))
        if isinstance(body, dict) and body.get('spec', {}).get('values', {}).get('image', {}).get('digest'):
            continue
        kept.append(entry)
    config['patches'] = kept + [{'path': 'versions.yaml'}]
    file.write_text(yaml.safe_dump(config, sort_keys=False))
print(f'Locked {len(releases)} installed Helm releases; OCI chart references retain their content digest.')
