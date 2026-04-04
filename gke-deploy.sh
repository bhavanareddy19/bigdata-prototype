#!/bin/bash
# ─────────────────────────────────────────────────────────────
# GKE Deployment Script — BigData Observability Platform
# ─────────────────────────────────────────────────────────────
# BUDGET: $50 GCP Education Credits
# COST:   ~$0.05-0.08/hr (~$1.50/day) using Spot VMs
#         → Can run ~30 days on $50
#
# IMPORTANT: Run gke-teardown.sh when you're done to stop charges!
#
# Usage:
#   1. Set your GCP project:  export GCP_PROJECT=your-project-id
#   2. Run:                   bash gke-deploy.sh
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - kubectl installed
#   - docker installed
# ─────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ────────────────────────────────────────────
GCP_PROJECT="${GCP_PROJECT:?Set GCP_PROJECT env var (e.g. export GCP_PROJECT=my-project-123)}"
GCP_REGION="${GCP_REGION:-us-central1}"
GKE_CLUSTER="${GKE_CLUSTER:-bigdata-platform}"
GKE_ZONE="${GKE_ZONE:-${GCP_REGION}-a}"
ARTIFACT_REPO="${ARTIFACT_REPO:-bigdata-images}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

REGISTRY="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/${ARTIFACT_REPO}"

echo "============================================="
echo "  BigData Platform — GKE Deployment"
echo "  BUDGET MODE: \$50 Education Credits"
echo "============================================="
echo "  Project:   ${GCP_PROJECT}"
echo "  Region:    ${GCP_REGION}"
echo "  Zone:      ${GKE_ZONE}"
echo "  Cluster:   ${GKE_CLUSTER}"
echo "  Registry:  ${REGISTRY}"
echo "  Est. cost: ~\$1.50/day (Spot VMs)"
echo "============================================="
echo ""
echo "Press Ctrl+C within 5 seconds to cancel..."
sleep 5

# ── Step 1: Enable required GCP APIs ────────────────────────
echo ""
echo "[1/8] Enabling GCP APIs..."
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  compute.googleapis.com \
  --project="${GCP_PROJECT}" --quiet

# ── Step 2: Create Artifact Registry repo ───────────────────
echo ""
echo "[2/8] Creating Artifact Registry repository..."
gcloud artifacts repositories describe "${ARTIFACT_REPO}" \
  --location="${GCP_REGION}" --project="${GCP_PROJECT}" 2>/dev/null || \
gcloud artifacts repositories create "${ARTIFACT_REPO}" \
  --repository-format=docker \
  --location="${GCP_REGION}" \
  --project="${GCP_PROJECT}" \
  --description="BigData Platform Docker images"

# Configure Docker to push to Artifact Registry
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

# ── Step 3: Build and push Docker images ────────────────────
echo ""
echo "[3/8] Building and pushing Docker images..."

echo "  Building bigdata-backend..."
docker build -t "${REGISTRY}/bigdata-backend:${IMAGE_TAG}" -f docker/Dockerfile.backend .
docker push "${REGISTRY}/bigdata-backend:${IMAGE_TAG}"

echo "  Building bigdata-frontend..."
docker build -t "${REGISTRY}/bigdata-frontend:${IMAGE_TAG}" -f docker/Dockerfile.frontend .
docker push "${REGISTRY}/bigdata-frontend:${IMAGE_TAG}"

echo "  Building bigdata-airflow..."
docker build -t "${REGISTRY}/bigdata-airflow:${IMAGE_TAG}" -f docker/Dockerfile.airflow .
docker push "${REGISTRY}/bigdata-airflow:${IMAGE_TAG}"

# ── Step 4: Create GKE cluster (BUDGET optimized) ───────────
echo ""
echo "[4/8] Creating GKE cluster (budget mode — Spot VMs)..."
if ! gcloud container clusters describe "${GKE_CLUSTER}" --zone="${GKE_ZONE}" --project="${GCP_PROJECT}" 2>/dev/null; then
  gcloud container clusters create "${GKE_CLUSTER}" \
    --zone="${GKE_ZONE}" \
    --project="${GCP_PROJECT}" \
    --num-nodes=2 \
    --machine-type=e2-standard-2 \
    --disk-size=30 \
    --spot \
    --no-enable-basic-auth \
    --release-channel=regular \
    --max-pods-per-node=30
  echo "  Cluster created (2x e2-standard-2 Spot VMs)."
  echo "  Cost: ~\$0.014/hr per node = ~\$0.67/day for cluster"
else
  echo "  Cluster already exists."
fi

# Get cluster credentials
gcloud container clusters get-credentials "${GKE_CLUSTER}" \
  --zone="${GKE_ZONE}" --project="${GCP_PROJECT}"

# ── Step 5: Create namespaces ───────────────────────────────
echo ""
echo "[5/8] Creating namespaces..."
kubectl apply -f k8s/namespaces.yaml

# ── Step 6: Patch image references and deploy ───────────────
echo ""
echo "[6/8] Patching image references for Artifact Registry..."

# Create temp patched manifests
TMPDIR=$(mktemp -d)
cp -r k8s/* "${TMPDIR}/"

# Replace local image names with Artifact Registry paths
for file in $(find "${TMPDIR}" -name "*.yaml"); do
  sed -i \
    -e "s|image: bigdata-backend:latest|image: ${REGISTRY}/bigdata-backend:${IMAGE_TAG}|g" \
    -e "s|image: bigdata-frontend:latest|image: ${REGISTRY}/bigdata-frontend:${IMAGE_TAG}|g" \
    -e "s|image: bigdata-airflow:latest|image: ${REGISTRY}/bigdata-airflow:${IMAGE_TAG}|g" \
    -e "s|imagePullPolicy: IfNotPresent|imagePullPolicy: Always|g" \
    "$file"
done

echo "  Deploying PostgreSQL..."
kubectl apply -f "${TMPDIR}/data/postgres.yaml"

echo "  Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=available deployment/postgres -n data --timeout=180s || echo "  (still starting, continuing...)"

echo "  Deploying Marquez..."
kubectl apply -f "${TMPDIR}/data/marquez.yaml"

echo "  Deploying Redis + Airflow..."
kubectl apply -f "${TMPDIR}/airflow/deployment.yaml"

echo "  Deploying Ollama..."
kubectl apply -f "${TMPDIR}/backend/ollama.yaml"

echo "  Deploying Backend..."
kubectl apply -f "${TMPDIR}/backend/deployment.yaml"

echo "  Deploying Frontend..."
kubectl apply -f "${TMPDIR}/backend/frontend.yaml"

# Clean up temp files
rm -rf "${TMPDIR}"

# ── Step 7: Apply Ingress ───────────────────────────────────
echo ""
echo "[7/8] Deploying Ingress..."
kubectl apply -f k8s/ingress.yaml

# ── Step 8: Verify deployment ──────────────────────────────
echo ""
echo "[8/8] Verifying deployments..."
echo ""
echo "--- Pods ---"
kubectl get pods --all-namespaces
echo ""
echo "--- Services ---"
kubectl get svc --all-namespaces
echo ""
echo "--- Ingress ---"
kubectl get ingress --all-namespaces

echo ""
echo "============================================="
echo "  Deployment complete!"
echo "============================================="
echo ""
echo "  IMPORTANT: Your \$50 credits are being consumed!"
echo "  Estimated burn rate: ~\$1.50/day"
echo "  Run 'bash gke-teardown.sh' when done to stop charges."
echo ""
echo "To check pod status:"
echo "  kubectl get pods -A"
echo ""
echo "To get external IP (takes 2-5 min for GCP to assign):"
echo "  kubectl get ingress -A"
echo ""
echo "To port-forward services locally for testing:"
echo "  kubectl port-forward svc/frontend 8501:8501 -n backend"
echo "  kubectl port-forward svc/backend 8000:8000 -n backend"
echo "  kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow"
echo "  kubectl port-forward svc/marquez-web 3000:3000 -n data"
echo ""
echo "To pull Ollama model after deployment:"
echo "  kubectl exec -it deploy/ollama -n backend -- ollama pull llama3.2:1b"
echo ""
echo "To check credit usage:"
echo "  https://console.cloud.google.com/billing"
echo ""
