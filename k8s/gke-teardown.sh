#!/usr/bin/env bash
# gke-teardown.sh — Remove all GKE resources.
#
# Usage:
#   GCP_PROJECT=my-project GCP_LOCATION=us-west1-c ./k8s/gke-teardown.sh

set -euo pipefail

: "${GCP_PROJECT:?Set GCP_PROJECT}"
: "${GCP_LOCATION:?Set GCP_LOCATION (region or zone, e.g. us-west1 or us-west1-c)}"
GCP_REGION=$(echo "$GCP_LOCATION" | sed 's/-[a-z]$//')
CLUSTER_NAME="${CLUSTER_NAME:-altex-cluster}"
REPO_NAME="${REPO_NAME:-altex}"
IP_NAME="${IP_NAME:-altex-ip}"

echo "=== Deleting K8s resources ==="
kubectl delete -k k8s/overlays/gcp/ --ignore-not-found 2>/dev/null || true

echo "=== Deleting GKE cluster ==="
gcloud container clusters delete "$CLUSTER_NAME" \
    --region="$GCP_LOCATION" \
    --project="$GCP_PROJECT" \
    --quiet

echo "=== Releasing static IP ==="
gcloud compute addresses delete "$IP_NAME" --global \
    --project="$GCP_PROJECT" \
    --quiet 2>/dev/null || true

echo "=== Deleting Artifact Registry repository ==="
gcloud artifacts repositories delete "$REPO_NAME" \
    --location="$GCP_REGION" \
    --project="$GCP_PROJECT" \
    --quiet 2>/dev/null || true

echo ""
echo "=== Teardown complete ==="
echo "  Remember to remove your DNS A record."
