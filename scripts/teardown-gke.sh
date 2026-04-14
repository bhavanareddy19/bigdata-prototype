#!/usr/bin/env bash
# Tear down everything the deploy script created (cluster + registry).
# Use this to STOP ALL CHARGES when you're done demoing.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-big-data-project-493204}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-us-central1-a}"
CLUSTER_NAME="${CLUSTER_NAME:-bigdata-lean}"
REPO_NAME="${REPO_NAME:-bigdata}"

gcloud config set project "$PROJECT_ID" >/dev/null

echo "This will DELETE cluster '$CLUSTER_NAME' in $ZONE, its LoadBalancer, PVs,"
echo "and Artifact Registry repo '$REPO_NAME' in $REGION."
read -r -p "Type 'yes' to continue: " CONFIRM
[[ "$CONFIRM" == "yes" ]] || { echo "Aborted."; exit 1; }

# Delete LoadBalancer services first so the GCP LB + forwarding rules are released
if gcloud container clusters describe "$CLUSTER_NAME" --zone="$ZONE" >/dev/null 2>&1; then
  gcloud container clusters get-credentials "$CLUSTER_NAME" --zone="$ZONE" || true
  echo "--- Deleting LoadBalancer services…"
  kubectl -n backend delete svc frontend --ignore-not-found --wait=true || true

  echo "--- Deleting cluster (takes 3–5 min)…"
  gcloud container clusters delete "$CLUSTER_NAME" --zone="$ZONE" --quiet
else
  echo "Cluster $CLUSTER_NAME not found — skipping."
fi

if gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" >/dev/null 2>&1; then
  echo "--- Deleting Artifact Registry repo…"
  gcloud artifacts repositories delete "$REPO_NAME" --location="$REGION" --quiet
fi

echo
echo "Teardown complete. Check billing dashboard in ~10 min to confirm no lingering resources:"
echo "  https://console.cloud.google.com/billing"
