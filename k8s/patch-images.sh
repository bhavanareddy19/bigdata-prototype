#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Patch K8s manifests to use GCP Artifact Registry image paths
# ─────────────────────────────────────────────────────────────
# Usage: REGISTRY=us-central1-docker.pkg.dev/my-project/bigdata-images bash k8s/patch-images.sh
# This creates patched copies in k8s/_gcp/ — originals are untouched.
set -euo pipefail

REGISTRY="${REGISTRY:?Set REGISTRY env var (e.g. us-central1-docker.pkg.dev/project/repo)}"
TAG="${IMAGE_TAG:-latest}"

SRC="k8s"
DEST="k8s/_gcp"
mkdir -p "${DEST}/backend" "${DEST}/airflow" "${DEST}/data"

echo "Patching manifests → ${DEST}/ with registry: ${REGISTRY}"

# Copy all manifests
cp "${SRC}/namespaces.yaml" "${DEST}/"
cp "${SRC}/data/postgres.yaml" "${DEST}/data/"
cp "${SRC}/data/marquez.yaml" "${DEST}/data/"
cp "${SRC}/backend/ollama.yaml" "${DEST}/backend/"

# Patch custom images: bigdata-backend, bigdata-frontend, bigdata-airflow
for file in backend/deployment.yaml backend/frontend.yaml airflow/deployment.yaml; do
  sed \
    -e "s|image: bigdata-backend:latest|image: ${REGISTRY}/bigdata-backend:${TAG}|g" \
    -e "s|image: bigdata-frontend:latest|image: ${REGISTRY}/bigdata-frontend:${TAG}|g" \
    -e "s|image: bigdata-airflow:latest|image: ${REGISTRY}/bigdata-airflow:${TAG}|g" \
    -e "s|imagePullPolicy: IfNotPresent|imagePullPolicy: Always|g" \
    "${SRC}/${file}" > "${DEST}/${file}"
  echo "  Patched ${file}"
done

# Patch ingress — remove nginx class, use GCE
sed \
  -e 's|ingressClassName: nginx|ingressClassName: gce|g' \
  -e '/nginx.ingress.kubernetes.io/d' \
  "${SRC}/ingress.yaml" > "${DEST}/ingress.yaml"
echo "  Patched ingress.yaml (nginx → gce)"

echo ""
echo "Done. Apply with:"
echo "  kubectl apply -f ${DEST}/namespaces.yaml"
echo "  kubectl apply -f ${DEST}/data/"
echo "  kubectl apply -f ${DEST}/airflow/"
echo "  kubectl apply -f ${DEST}/backend/"
echo "  kubectl apply -f ${DEST}/ingress.yaml"
