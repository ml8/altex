# Kubernetes Deployment

Deploy altex to Kubernetes with horizontal autoscaling and TLS.

## Architecture

```
Internet → Cloud DNS → GKE Ingress (TLS) → Service → Pods (1–5, HPA)
```

The app is **fully stateless** in K8s mode (`ALTEX_STORAGE=inline`):
each request processes files in a temp directory, returns the tagged PDF
as base64 in the JSON response, and cleans up.  No filesystem state
shared between requests or replicas.

## Prerequisites

- `gcloud` CLI authenticated with a GCP project
- `kubectl` configured (auto-configured by `gke-setup.sh`)
- `docker` for building images
- A domain name you control (for TLS cert provisioning)

## Quick Start (GCP/GKE)

```bash
# Set your project and region
export GCP_PROJECT=my-project-123
export GCP_LOCATION=us-west1  # or us-west1-c for zonal clusters

# 1. Create cluster, registry, static IP (one-time)
make gke-setup

# Or use an existing cluster:
CLUSTER_NAME=my-cluster SKIP_CLUSTER_CREATE=1 make gke-setup

# 2. Point DNS: altex.yourdomain.com → <static IP from step 1>

# 3. Edit k8s/overlays/gcp/managed-cert.yaml — set your domain
# 4. Edit k8s/overlays/gcp/kustomization.yaml — set your project ID

# 5. Build, push, deploy
make gke-deploy

# 6. Check status
make gke-status

# Cleanup (deletes everything)
make gke-teardown
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALTEX_STORAGE` | `local` | Storage mode: `local` (filesystem) or `inline` (base64 in JSON) |
| `PORT` | `5000` | HTTP listen port (set by gunicorn CMD) |

The K8s deployment sets `ALTEX_STORAGE=inline` for stateless operation.
Local development uses the default `local` mode.

### GKE Variables

Set these before running `gke-setup.sh` or `gke-deploy.sh`:

| Variable | Example | Description |
|----------|---------|-------------|
| `GCP_PROJECT` | `my-project-123` | GCP project ID |
| `GCP_LOCATION` | `us-west1` or `us-west1-c` | GCP region or zone for cluster; region auto-derived for registry |
| `CLUSTER_NAME` | `altex-cluster` | GKE cluster name (default) |
| `SKIP_CLUSTER_CREATE` | `1` | Set to `1` to skip cluster creation (use existing) |
| `REPO_NAME` | `altex` | Artifact Registry repository name (default) |
| `IP_NAME` | `altex-ip` | Static IP resource name (default) |

### Customizing the Deployment

Edit `k8s/overlays/gcp/kustomization.yaml` to set the image reference:

```yaml
images:
  - name: altex
    newName: us-central1-docker.pkg.dev/YOUR_PROJECT/altex/altex
    newTag: latest
```

Edit `k8s/overlays/gcp/managed-cert.yaml` to set your domain:

```yaml
spec:
  domains:
    - altex.yourdomain.com
```

## File Structure

```
k8s/
├── base/                        # Cloud-agnostic manifests
│   ├── kustomization.yaml       # Kustomize base
│   ├── deployment.yaml          # Deployment (pods, probes, resources)
│   ├── service.yaml             # ClusterIP Service
│   └── hpa.yaml                 # HorizontalPodAutoscaler (1–5 replicas)
├── overlays/
│   └── gcp/                     # GCP/GKE-specific overlay
│       ├── kustomization.yaml   # Image override + GCP resources
│       ├── ingress.yaml         # GKE Ingress (external ALB + static IP)
│       └── managed-cert.yaml    # Google-managed TLS certificate
├── gke-setup.sh                 # Create cluster, registry, static IP
├── gke-deploy.sh                # Build, push, deploy
├── gke-teardown.sh              # Delete all resources
└── README.md                    # This file
```

The base manifests work on any Kubernetes cluster (minikube, kind, EKS,
AKS).  The GCP overlay adds GKE-specific resources.

## DNS Setup

1. Reserve a global static IP:
   ```bash
   gcloud compute addresses create altex-ip --global
   gcloud compute addresses describe altex-ip --global --format='value(address)'
   ```

2. Add an A record at your DNS provider:
   ```
   altex.yourdomain.com  →  A  →  <static IP>
   ```

3. Google auto-provisions and renews the TLS certificate once DNS resolves
   (~15–30 minutes).

## Design Decisions

**GKE Autopilot** — Google manages nodes, scaling, and security.  No
node pool configuration needed.  Recommended for stateless web apps.
([GKE Autopilot docs](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview))

**Gunicorn** — Production WSGI server replacing Flask's dev server.
Runs 2 workers per pod with 120s timeout for PDF processing.

**Inline storage** — PDF returned as base64 in the API response,
eliminating cross-request filesystem state.  Enables true horizontal
scaling with no sticky sessions or shared storage.

**Google-managed certs** — Zero-maintenance TLS.  Google provisions DV
certificates and handles renewal automatically.
([Managed certs docs](https://cloud.google.com/kubernetes-engine/docs/how-to/managed-certs))

**Kustomize overlays** — Base manifests are cloud-agnostic.  The GCP
overlay adds only GKE-specific resources (Ingress annotations,
ManagedCertificate).  Easy to add AWS/Azure overlays later.
