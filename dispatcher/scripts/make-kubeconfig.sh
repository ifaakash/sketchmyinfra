#!/usr/bin/env bash
# Build a kubeconfig for the dispatcher ServiceAccount (k8s/agent/dispatcher-rbac.yaml).
# Run on the Pi (or anywhere with admin kubectl access):
#
#   dispatcher/scripts/make-kubeconfig.sh https://<pi-ip>:6443 > dispatcher/secrets/kubeconfig
#
# The server URL must be an address in the k3s API cert's SANs. From inside a
# compose container 127.0.0.1 is the container itself and host.docker.internal
# isn't in the cert — use the Pi's LAN/Tailscale IP (or add `--tls-san` to k3s).
# Check SANs: openssl s_client -connect <ip>:6443 </dev/null 2>/dev/null \
#               | openssl x509 -noout -ext subjectAltName
set -euo pipefail

SERVER="${1:?usage: $0 https://<pi-ip>:6443}"
NS=agent
SECRET=dispatcher-token

TOKEN=$(kubectl -n "$NS" get secret "$SECRET" -o jsonpath='{.data.token}' | base64 -d)
CA=$(kubectl -n "$NS" get secret "$SECRET" -o jsonpath='{.data.ca\.crt}')

if [ -z "$TOKEN" ]; then
  echo "token not populated yet — did you apply k8s/agent/dispatcher-rbac.yaml?" >&2
  exit 1
fi

cat <<EOF
apiVersion: v1
kind: Config
clusters:
  - name: k3s
    cluster:
      server: ${SERVER}
      certificate-authority-data: ${CA}
users:
  - name: dispatcher
    user:
      token: ${TOKEN}
contexts:
  - name: dispatcher@k3s
    context:
      cluster: k3s
      user: dispatcher
      namespace: ${NS}
current-context: dispatcher@k3s
EOF
