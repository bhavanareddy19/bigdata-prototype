#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# BigData Platform — Full GKE Deployment Script
#
# Deploys: frontend, backend, airflow, postgres, marquez (lineage)
# One-shot & re-run safe (idempotent).
#
# Usage:
#   cd <repo-root>
#   ./scripts/deploy-gke.sh
#
# Required tools: gcloud, kubectl, docker
# Required env:   GOOGLE_API_KEY  (auto-loaded from .env if present)
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Load .env for GOOGLE_API_KEY and other vars
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a; source "$REPO_ROOT/.env"; set +a
fi

PROJECT_ID="${PROJECT_ID:-big-data-project-493204}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-us-central1-a}"
CLUSTER_NAME="${CLUSTER_NAME:-bigdata-lean}"
REPO_NAME="${REPO_NAME:-bigdata}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-4}"
NODE_COUNT="${NODE_COUNT:-2}"
USE_SPOT="${USE_SPOT:-true}"

if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
  echo "ERROR: GOOGLE_API_KEY not set. Add it to .env or export it." >&2
  exit 1
fi

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
TAG="${TAG:-$(date +%Y%m%d-%H%M%S)}"
IMG_BACKEND="${REGISTRY}/backend:${TAG}"
IMG_FRONTEND="${REGISTRY}/frontend:${TAG}"
IMG_AIRFLOW="${REGISTRY}/airflow:${TAG}"

echo "════════════════════════════════════════════"
echo " Project : $PROJECT_ID"
echo " Region  : $REGION  Zone: $ZONE"
echo " Cluster : $CLUSTER_NAME"
echo " Tag     : $TAG"
echo "════════════════════════════════════════════"

# ── 1. GCP project + APIs ────────────────────────────────────────
echo
echo "▶ [1/8] Enabling GCP APIs…"
gcloud config set project "$PROJECT_ID" --quiet
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  compute.googleapis.com \
  --quiet

# ── 2. Artifact Registry ─────────────────────────────────────────
echo
echo "▶ [2/8] Artifact Registry…"
if ! gcloud artifacts repositories describe "$REPO_NAME" \
    --location="$REGION" --quiet >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --description="BigData Platform images" \
    --quiet
  echo "  Created repo $REPO_NAME"
else
  echo "  Repo $REPO_NAME already exists"
fi
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── 3. GKE cluster ───────────────────────────────────────────────
echo
echo "▶ [3/8] GKE cluster…"
if ! gcloud container clusters describe "$CLUSTER_NAME" \
    --zone="$ZONE" --quiet >/dev/null 2>&1; then
  echo "  Creating cluster (takes ~5 min)…"
  SPOT_FLAG=""
  [[ "$USE_SPOT" == "true" ]] && SPOT_FLAG="--spot"
  gcloud container clusters create "$CLUSTER_NAME" \
    --zone="$ZONE" \
    --num-nodes="$NODE_COUNT" \
    --machine-type="$MACHINE_TYPE" \
    --disk-size=50 \
    --disk-type=pd-standard \
    --release-channel=regular \
    --enable-ip-alias \
    --no-enable-master-authorized-networks \
    $SPOT_FLAG \
    --quiet
else
  echo "  Cluster $CLUSTER_NAME already exists"
fi
gcloud container clusters get-credentials "$CLUSTER_NAME" --zone="$ZONE" --quiet

# ── 4. Build + push images ──────────────────────────────────────
echo
echo "▶ [4/8] Building & pushing images…"

echo "  backend → $IMG_BACKEND"
docker build -t "$IMG_BACKEND" -f "$REPO_ROOT/docker/Dockerfile.backend" "$REPO_ROOT"
docker push "$IMG_BACKEND"

echo "  frontend → $IMG_FRONTEND"
docker build -t "$IMG_FRONTEND" -f "$REPO_ROOT/docker/Dockerfile.frontend" "$REPO_ROOT"
docker push "$IMG_FRONTEND"

echo "  airflow → $IMG_AIRFLOW"
docker build -t "$IMG_AIRFLOW" -f "$REPO_ROOT/docker/Dockerfile.airflow" "$REPO_ROOT"
docker push "$IMG_AIRFLOW"

# ── 5. Namespaces + RBAC ────────────────────────────────────────
echo
echo "▶ [5/8] Namespaces + RBAC…"
kubectl apply -f "$REPO_ROOT/k8s/namespaces.yaml"
kubectl apply -f "$REPO_ROOT/k8s/backend/rbac.yaml"

# ── 6. Data layer: Postgres + Marquez ───────────────────────────
echo
echo "▶ [6/8] Data layer (Postgres + Marquez)…"
kubectl apply -f "$REPO_ROOT/k8s/data/postgres.yaml"
echo "  Waiting for Postgres…"
kubectl -n data rollout status statefulset/postgres --timeout=180s

kubectl apply -f "$REPO_ROOT/k8s/data/marquez.yaml"
echo "  Waiting for Marquez API (may take ~2 min on first start)…"
kubectl -n data rollout status deployment/marquez-api --timeout=300s || true
kubectl -n data rollout status deployment/marquez-web --timeout=120s || true

# ── 7. Backend + Airflow ─────────────────────────────────────────
echo
echo "▶ [7/8] Backend + Airflow + Frontend…"

# Inject GOOGLE_API_KEY as a K8s secret
kubectl -n backend create secret generic backend-secrets \
  --from-literal=GOOGLE_API_KEY="$GOOGLE_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Render image tags into manifests and apply
sed "s|IMAGE_BACKEND|$IMG_BACKEND|g" \
  "$REPO_ROOT/k8s/backend/deployment.yaml" | kubectl apply -f -

sed "s|IMAGE_AIRFLOW|$IMG_AIRFLOW|g" \
  "$REPO_ROOT/k8s/airflow/deployment.yaml" | kubectl apply -f -

sed "s|IMAGE_FRONTEND|$IMG_FRONTEND|g" \
  "$REPO_ROOT/k8s/backend/frontend.yaml" | kubectl apply -f -

# ── 8. Wait for rollouts ─────────────────────────────────────────
echo
echo "▶ [8/8] Waiting for rollouts…"
kubectl -n backend rollout status deployment/backend   --timeout=300s || true
kubectl -n backend rollout status deployment/frontend  --timeout=300s || true
kubectl -n airflow rollout status deployment/airflow-webserver --timeout=600s || true
kubectl -n airflow rollout status deployment/airflow-scheduler --timeout=300s || true

# ── Done — print access info ─────────────────────────────────────
echo
echo "════════════════════════════════════════════"
echo " Waiting for LoadBalancer IP…"
echo "════════════════════════════════════════════"

LB_IP=""
for i in {1..36}; do
  LB_IP=$(kubectl -n backend get svc frontend \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  [[ -n "$LB_IP" ]] && break
  echo "  Attempt $i/36 — not assigned yet, waiting 10s…"
  sleep 10
done

echo
if [[ -n "$LB_IP" ]]; then
  echo "✅ Deployment complete!"
  echo
  echo "  BigData Platform UI : http://$LB_IP/"
  echo "  Airflow UI          : http://$LB_IP/airflow/   (admin / admin)"
  echo "  Marquez UI          : http://$LB_IP/marquez/"
  echo "  Backend health      : http://$LB_IP/health"
else
  echo "⚠  LoadBalancer IP not yet assigned."
  echo "   Run: kubectl -n backend get svc frontend -w"
fi

echo
echo "Useful commands:"
echo "  kubectl get pods -A"
echo "  kubectl -n backend logs deploy/backend -f"
echo "  kubectl -n airflow logs deploy/airflow-webserver -f"
echo "  kubectl -n data    logs deploy/marquez-api -f"
