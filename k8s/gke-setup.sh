#!/usr/bin/env bash
# gke-setup.sh — One-time GKE infrastructure setup.
#
# Creates (as needed):
#   - Autopilot cluster (skipped if CLUSTER_NAME already exists or
#     SKIP_CLUSTER_CREATE=1)
#   - Artifact Registry repository
#   - Global static IP for Ingress
#
# Usage:
#   GCP_PROJECT=my-project GCP_LOCATION=us-west1-c ./k8s/gke-setup.sh
#
#   # Use an existing cluster:
#   CLUSTER_NAME=my-cluster SKIP_CLUSTER_CREATE=1 \
#     GCP_PROJECT=my-project GCP_LOCATION=us-west1-c ./k8s/gke-setup.sh

set -euo pipefail

: "${GCP_PROJECT:?Set GCP_PROJECT}"
: "${GCP_LOCATION:?Set GCP_LOCATION (region or zone, e.g. us-west1 or us-west1-c)}"
# Derive region from location (strip zone suffix if present: us-west1-c → us-west1).
GCP_REGION=$(echo "$GCP_LOCATION" | sed 's/-[a-z]$//')
CLUSTER_NAME="${CLUSTER_NAME:-altex-cluster}"
REPO_NAME="${REPO_NAME:-altex}"
IP_NAME="${IP_NAME:-altex-ip}"
SKIP_CLUSTER_CREATE="${SKIP_CLUSTER_CREATE:-0}"

# -- Cluster ---------------------------------------------------------------
if [ "$SKIP_CLUSTER_CREATE" = "1" ]; then
    echo "=== Using existing cluster: $CLUSTER_NAME ==="
else
    # Check if cluster already exists.
    if gcloud container clusters describe "$CLUSTER_NAME" \
        --region="$GCP_LOCATION" --project="$GCP_PROJECT" \
        >/dev/null 2>&1; then
        echo "=== Cluster $CLUSTER_NAME already exists, skipping create ==="
    else
        echo "=== Creating GKE Autopilot cluster ==="
        gcloud container clusters create-auto "$CLUSTER_NAME" \
            --region="$GCP_LOCATION" \
            --project="$GCP_PROJECT"
    fi
fi

# Configure kubectl to use the cluster.
gcloud container clusters get-credentials "$CLUSTER_NAME" \
    --region="$GCP_LOCATION" \
    --project="$GCP_PROJECT"

echo "=== Creating Artifact Registry repository ==="
if gcloud artifacts repositories describe "$REPO_NAME" \
    --location="$GCP_REGION" --project="$GCP_PROJECT" \
    >/dev/null 2>&1; then
    echo "  (repository already exists)"
else
    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=docker \
        --location="$GCP_REGION" \
        --project="$GCP_PROJECT"
fi

echo "=== Configuring Docker authentication ==="
gcloud auth configure-docker "$GCP_REGION-docker.pkg.dev" --quiet

echo "=== Reserving global static IP ==="
gcloud compute addresses create "$IP_NAME" --global \
    --project="$GCP_PROJECT" \
    2>/dev/null || echo "  (IP already reserved)"

IP=$(gcloud compute addresses describe "$IP_NAME" --global \
    --project="$GCP_PROJECT" --format='value(address)')

echo ""
echo "=== Setup complete ==="
echo "  Cluster:  $CLUSTER_NAME ($GCP_REGION)"
echo "  Registry: $GCP_REGION-docker.pkg.dev/$GCP_PROJECT/$REPO_NAME"
echo "  Static IP: $IP"
echo ""
echo "Next steps:"
echo "  1. Point your DNS A record to $IP"
echo "  2. Update k8s/overlays/gcp/managed-cert.yaml with your domain"
echo "  3. Update k8s/overlays/gcp/kustomization.yaml with your project ID"
echo "  4. Run: make gke-deploy"
