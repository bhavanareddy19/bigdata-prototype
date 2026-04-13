#!/usr/bin/env bash
# Deploy the BigData Platform (lean variant) to a cheap GKE cluster.
#
# One-shot: creates cluster + registry, builds images, pushes them, applies manifests.
# Re-run safe: idempotent — skips resources that already exist, rolls out new images.
#
# Usage:
#   export GOOGLE_API_KEY=...        # or put it in .env next to this script
#   ./scripts/deploy-gke.sh
#
# Required tools: gcloud, kubectl, docker

set -euo pipefail

# ── Config (override via env) ────────────────────────────────
PROJECT_ID="${PROJECT_ID:-big-data-project-493204}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-us-central1-a}"
CLUSTER_NAME="${CLUSTER_NAME:-bigdata-lean}"
REPO_NAME="${REPO_NAME:-bigdata}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-2}"
NODE_COUNT="${NODE_COUNT:-1}"
USE_SPOT="${USE_SPOT:-true}"

# ── Load API key ─────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$REPO_ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a; source "$REPO_ROOT/.env"; set +a
fi
if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
  echo "ERROR: GOOGLE_API_KEY not set. Put it in .env or export it." >&2
  exit 1
fi

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
TAG="${TAG:-$(date +%Y%m%d-%H%M%S)}"
IMG_BACKEND="${REGISTRY}/backend:${TAG}"
IMG_FRONTEND="${REGISTRY}/frontend:${TAG}"
IMG_AIRFLOW="${REGISTRY}/airflow:${TAG}"

echo "=== Project: $PROJECT_ID | Region: $REGION | Cluster: $CLUSTER_NAME ==="
echo "=== Tag: $TAG ==="

# ── 1. Set project + enable required APIs ───────────────────
gcloud config set project "$PROJECT_ID" >/dev/null
echo "--- Enabling APIs (idempotent)…"
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  compute.googleapis.com

# ── 2. Create Artifact Registry repo (idempotent) ───────────
if ! gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" >/dev/null 2>&1; then
  echo "--- Creating Artifact Registry repo $REPO_NAME in $REGION…"
  gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker --location="$REGION" \
    --description="BigData platform images"
else
  echo "--- Artifact Registry repo $REPO_NAME exists."
fi
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── 3. Create GKE zonal Standard cluster (free control plane) ─
if ! gcloud container clusters describe "$CLUSTER_NAME" --zone="$ZONE" >/dev/null 2>&1; then
  echo "--- Creating GKE cluster (this takes ~5 min)…"
  SPOT_FLAG=""
  [[ "$USE_SPOT" == "true" ]] && SPOT_FLAG="--spot"
  gcloud container clusters create "$CLUSTER_NAME" \
    --zone="$ZONE" \
    --num-nodes="$NODE_COUNT" \
    --machine-type="$MACHINE_TYPE" \
    --disk-size=30 --disk-type=pd-standard \
    --release-channel=regular \
    --enable-ip-alias \
    --no-enable-master-authorized-networks \
    $SPOT_FLAG
else
  echo "--- Cluster $CLUSTER_NAME already exists."
fi
gcloud container clusters get-credentials "$CLUSTER_NAME" --zone="$ZONE"

# ── 4. Build + push images ──────────────────────────────────
echo "--- Building & pushing backend image…"
docker build -t "$IMG_BACKEND"  -f "$REPO_ROOT/docker/Dockerfile.backend"  "$REPO_ROOT"
docker push "$IMG_BACKEND"

echo "--- Building & pushing frontend image…"
docker build -t "$IMG_FRONTEND" -f "$REPO_ROOT/docker/Dockerfile.frontend" "$REPO_ROOT"
docker push "$IMG_FRONTEND"

echo "--- Building & pushing airflow image…"
docker build -t "$IMG_AIRFLOW"  -f "$REPO_ROOT/docker/Dockerfile.airflow"  "$REPO_ROOT"
docker push "$IMG_AIRFLOW"

# ── 5. Apply manifests ──────────────────────────────────────
echo "--- Applying namespaces…"
kubectl apply -f "$REPO_ROOT/k8s/namespaces.yaml"

echo "--- Applying RBAC…"
kubectl apply -f "$REPO_ROOT/k8s/backend/rbac.yaml"

echo "--- Applying Postgres…"
kubectl apply -f "$REPO_ROOT/k8s/data/postgres.yaml"
kubectl -n data rollout status statefulset/postgres --timeout=180s

echo "--- Creating backend secret with Gemini key…"
kubectl -n backend create secret generic backend-secrets \
  --from-literal=GOOGLE_API_KEY="$GOOGLE_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "--- Rendering + applying backend (image=$IMG_BACKEND)…"
sed "s|IMAGE_BACKEND|$IMG_BACKEND|g" "$REPO_ROOT/k8s/backend/deployment.yaml" \
  | kubectl apply -f -

echo "--- Rendering + applying airflow (image=$IMG_AIRFLOW)…"
sed "s|IMAGE_AIRFLOW|$IMG_AIRFLOW|g" "$REPO_ROOT/k8s/airflow/deployment.yaml" \
  | kubectl apply -f -

echo "--- Rendering + applying frontend (image=$IMG_FRONTEND)…"
sed "s|IMAGE_FRONTEND|$IMG_FRONTEND|g" "$REPO_ROOT/k8s/backend/frontend.yaml" \
  | kubectl apply -f -

# ── 6. Wait for rollouts ────────────────────────────────────
echo "--- Waiting for rollouts…"
kubectl -n backend rollout status deployment/backend   --timeout=300s || true
kubectl -n backend rollout status deployment/frontend  --timeout=300s || true
kubectl -n airflow rollout status deployment/airflow-webserver --timeout=600s || true
kubectl -n airflow rollout status deployment/airflow-scheduler --timeout=300s || true

# ── 7. Print access info ────────────────────────────────────
echo
echo "=== Deployment complete ==="
echo "Getting external LB IP (may take 1–2 minutes)…"
for i in {1..30}; do
  LB_IP=$(kubectl -n backend get svc frontend -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  [[ -n "$LB_IP" ]] && break
  sleep 10
done

if [[ -n "$LB_IP" ]]; then
  echo
  echo "Frontend:   http://$LB_IP/"
  echo "Backend:    http://$LB_IP/health"
  echo "Airflow UI: http://$LB_IP/airflow/  (admin / admin)"
else
  echo "LB IP not yet assigned. Run: kubectl -n backend get svc frontend -w"
fi

echo
echo "Useful commands:"
echo "  kubectl get pods -A"
echo "  kubectl -n backend logs deploy/backend -f"
echo "  kubectl -n airflow logs deploy/airflow-scheduler -f"
