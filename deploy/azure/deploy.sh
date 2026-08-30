#!/usr/bin/env bash
#
# Build, push and roll out City Hospital on AKS.
#
#   ./deploy/azure/deploy.sh -g my-rg -p cityhosp -t 0.1.0 -H clinic.example.com
#
# Assumes the infrastructure already exists:
#   az deployment group create -g my-rg -f deploy/azure/main.bicep \
#      -p namePrefix=cityhosp postgresAdminPassword='<strong>'
#
# The script is idempotent — re-running it with a new -t rolls a new image out.
# It never creates or overwrites the application Secret; see docs/deployment.md.

set -euo pipefail

RESOURCE_GROUP=""
PREFIX=""
TAG="$(date +%Y%m%d-%H%M%S)"
HOSTNAME_FQDN=""
NAMESPACE="cityhospital"

usage() {
  sed -n '2,14p' "$0"
  exit "${1:-0}"
}

while getopts "g:p:t:H:n:h" opt; do
  case "$opt" in
    g) RESOURCE_GROUP="$OPTARG" ;;
    p) PREFIX="$OPTARG" ;;
    t) TAG="$OPTARG" ;;
    H) HOSTNAME_FQDN="$OPTARG" ;;
    n) NAMESPACE="$OPTARG" ;;
    h) usage 0 ;;
    *) usage 2 ;;
  esac
done

[ -n "$RESOURCE_GROUP" ] || { echo "-g <resource-group> is required" >&2; usage 2; }
[ -n "$PREFIX" ]         || { echo "-p <namePrefix> is required" >&2; usage 2; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OVERLAY="$ROOT/deploy/k8s/overlays/aks"

step() { printf '\033[36m==> %s\033[0m\n' "$1"; }

for tool in az kubectl kustomize; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is not installed" >&2; exit 1; }
done

# --------------------------------------------------------------------------- #
# Read what the Bicep deployment created
# --------------------------------------------------------------------------- #
step "Reading infrastructure outputs from $RESOURCE_GROUP"
ACR_NAME="$(az acr list -g "$RESOURCE_GROUP" --query "[0].name" -o tsv)"
ACR_SERVER="$(az acr show -n "$ACR_NAME" --query loginServer -o tsv)"
AKS_NAME="$(az aks list -g "$RESOURCE_GROUP" --query "[0].name" -o tsv)"
IDENTITY_CLIENT_ID="$(az identity show -g "$RESOURCE_GROUP" -n "${PREFIX}-workload-id" --query clientId -o tsv)"

echo "    registry : $ACR_SERVER"
echo "    cluster  : $AKS_NAME"
echo "    identity : $IDENTITY_CLIENT_ID"
echo "    tag      : $TAG"

# --------------------------------------------------------------------------- #
# Build in ACR (no local Docker daemon needed)
# --------------------------------------------------------------------------- #
step "Building cityhospital-backend:$TAG"
az acr build \
  --registry "$ACR_NAME" \
  --image "cityhospital-backend:$TAG" \
  --file docker/backend.Dockerfile \
  "$ROOT"

step "Building cityhospital-web:$TAG"
# NEXT_PUBLIC_API_BASE is deliberately left empty: the browser then calls its
# own origin, and the ingress routes /api and /ws to the gateway. That is what
# keeps this image environment-agnostic.
az acr build \
  --registry "$ACR_NAME" \
  --image "cityhospital-web:$TAG" \
  --file docker/frontend.Dockerfile \
  --build-arg NEXT_PUBLIC_API_BASE="" \
  --build-arg NEXT_PUBLIC_WS_BASE="" \
  "$ROOT"

# --------------------------------------------------------------------------- #
# Point the overlay at this build
# --------------------------------------------------------------------------- #
step "Preparing the AKS overlay"
az aks get-credentials -g "$RESOURCE_GROUP" -n "$AKS_NAME" --overwrite-existing

pushd "$OVERLAY" >/dev/null
kustomize edit set image \
  "cityhospital-backend=$ACR_SERVER/cityhospital-backend:$TAG" \
  "cityhospital-web=$ACR_SERVER/cityhospital-web:$TAG"
popd >/dev/null

# The service account has to carry the real client id or the pods get no token.
sed -i.bak "s|azure.workload.identity/client-id: .*|azure.workload.identity/client-id: \"$IDENTITY_CLIENT_ID\"|" \
  "$OVERLAY/serviceaccount.yaml"
rm -f "$OVERLAY/serviceaccount.yaml.bak"

if [ -n "$HOSTNAME_FQDN" ]; then
  step "Setting the ingress host to $HOSTNAME_FQDN"
  sed -i.bak "s|cityhospital\.example\.com|$HOSTNAME_FQDN|g" "$OVERLAY/ingress-patch.yaml"
  sed -i.bak "s|https://cityhospital\.example\.com|https://$HOSTNAME_FQDN|g" "$OVERLAY/kustomization.yaml"
  rm -f "$OVERLAY"/*.bak
fi

# --------------------------------------------------------------------------- #
# Guard: the Secret is created out of band, never by this script
# --------------------------------------------------------------------------- #
if ! kubectl -n "$NAMESPACE" get secret backend-secrets >/dev/null 2>&1; then
  cat >&2 <<EOF

  The 'backend-secrets' Secret does not exist in namespace '$NAMESPACE'.
  Create it before deploying — see docs/deployment.md. For example:

    kubectl create namespace $NAMESPACE
    kubectl -n $NAMESPACE create secret generic backend-secrets \\
      --from-literal=DATABASE_URL='postgresql+psycopg://...?sslmode=require' \\
      --from-literal=REDIS_URL='rediss://:<key>@<host>:6380/0' \\
      --from-literal=JWT_SECRET="\$(openssl rand -hex 32)" \\
      --from-literal=OPENAI_API_KEY='sk-...'

EOF
  exit 1
fi

# --------------------------------------------------------------------------- #
# Roll out
# --------------------------------------------------------------------------- #
step "Applying manifests"
kustomize build "$OVERLAY" | kubectl apply -f -

step "Waiting for the schema job"
kubectl -n "$NAMESPACE" wait --for=condition=complete job/db-schema --timeout=300s

step "Waiting for the rollout"
for deployment in gateway agent-worker mcp web; do
  kubectl -n "$NAMESPACE" rollout status "deployment/$deployment" --timeout=300s
done

step "Deployed"
kubectl -n "$NAMESPACE" get pods,svc,ingress
echo
echo "  Check the gateway sees its dependencies:"
echo "    kubectl -n $NAMESPACE exec deploy/gateway -- python -c \\"
echo "      \"import urllib.request,json;print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health')))\""
echo
echo "  Expect \"redis\": true and \"event_bus\": \"RedisStreamEventBus\"."
