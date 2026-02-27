#!/usr/bin/env bash
# gke-deploy.sh — Build, push, and deploy to GKE.
#
# Usage:
#   GCP_PROJECT=my-project GCP_LOCATION=us-west1-c ./k8s/gke-deploy.sh

set -euo pipefail

: "${GCP_PROJECT:?Set GCP_PROJECT}"
: "${GCP_LOCATION:?Set GCP_LOCATION (region or zone, e.g. us-west1 or us-west1-c)}"
GCP_REGION=$(echo "$GCP_LOCATION" | sed 's/-[a-z]$//')
REPO_NAME="${REPO_NAME:-altex}"
IMAGE="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT/$REPO_NAME/altex:latest"

echo "=== Building Docker image (linux/amd64) ==="
# --platform ensures the image runs on GKE (amd64) when built on Apple Silicon.
# --provenance/--sbom=false avoid attestation manifests that Artifact Registry rejects.
docker build --platform=linux/amd64 --provenance=false --sbom=false -t "$IMAGE" .

echo "=== Pushing to Artifact Registry ==="
docker push "$IMAGE"

echo "=== Deploying to GKE ==="
# Update the image reference in the kustomization overlay.
cd "$(dirname "$0")/overlays/gcp"
kubectl kustomize edit set image "altex=$IMAGE" 2>/dev/null \
    || sed -i '' "s|newName:.*|newName: ${IMAGE%:*}|;s|newTag:.*|newTag: ${IMAGE##*:}|" kustomization.yaml
cd -

kubectl apply -k k8s/overlays/gcp/

echo ""
echo "=== Deploy complete ==="
echo "  Image: $IMAGE"
echo ""
echo "Check status:"
echo "  kubectl get pods -l app=altex"
echo "  kubectl describe managedcertificate altex-cert"
echo "  kubectl get ingress altex"
