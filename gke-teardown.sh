#!/bin/bash
# ─────────────────────────────────────────────────────────────
# GKE Teardown Script — STOP ALL CHARGES
# ─────────────────────────────────────────────────────────────
# Run this when you're done to stop burning your $50 credits!
#
# Usage: bash gke-teardown.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

GCP_PROJECT="${GCP_PROJECT:?Set GCP_PROJECT env var}"
GCP_REGION="${GCP_REGION:-us-central1}"
GKE_CLUSTER="${GKE_CLUSTER:-bigdata-platform}"
GKE_ZONE="${GKE_ZONE:-${GCP_REGION}-a}"
ARTIFACT_REPO="${ARTIFACT_REPO:-bigdata-images}"

echo "============================================="
echo "  BigData Platform — TEARDOWN"
echo "============================================="
echo "  This will DELETE:"
echo "    - GKE cluster: ${GKE_CLUSTER}"
echo "    - All persistent disks attached to the cluster"
echo "    - Artifact Registry repo: ${ARTIFACT_REPO}"
echo ""
echo "  This will STOP all charges."
echo "============================================="
echo ""
read -p "Are you sure? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Cancelled."
  exit 0
fi

echo ""
echo "[1/3] Deleting GKE cluster..."
gcloud container clusters delete "${GKE_CLUSTER}" \
  --zone="${GKE_ZONE}" \
  --project="${GCP_PROJECT}" \
  --quiet
echo "  Cluster deleted."

echo ""
echo "[2/3] Cleaning up persistent disks..."
# Delete any orphaned disks from PVCs
DISKS=$(gcloud compute disks list --project="${GCP_PROJECT}" --filter="zone:${GKE_ZONE}" --format="value(name)" 2>/dev/null || true)
if [ -n "$DISKS" ]; then
  echo "  Found orphaned disks:"
  echo "$DISKS"
  read -p "  Delete these disks? (yes/no): " DEL_DISKS
  if [ "$DEL_DISKS" = "yes" ]; then
    for disk in $DISKS; do
      gcloud compute disks delete "$disk" --zone="${GKE_ZONE}" --project="${GCP_PROJECT}" --quiet || true
    done
    echo "  Disks deleted."
  fi
else
  echo "  No orphaned disks found."
fi

echo ""
echo "[3/3] Deleting Artifact Registry images (optional)..."
read -p "Delete Docker images from Artifact Registry? (yes/no): " DEL_IMAGES
if [ "$DEL_IMAGES" = "yes" ]; then
  gcloud artifacts repositories delete "${ARTIFACT_REPO}" \
    --location="${GCP_REGION}" \
    --project="${GCP_PROJECT}" \
    --quiet || true
  echo "  Artifact Registry repo deleted."
else
  echo "  Skipped. Images kept in Artifact Registry (minimal cost)."
fi

echo ""
echo "============================================="
echo "  Teardown complete!"
echo "  All GKE charges have stopped."
echo ""
echo "  Check remaining credits at:"
echo "  https://console.cloud.google.com/billing"
echo "============================================="
