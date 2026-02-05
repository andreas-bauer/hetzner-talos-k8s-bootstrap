# Talos Linux Kubernetes on Hetzner Cloud with Pulumi

Deploy a multi-node Talos Linux Kubernetes cluster on Hetzner Cloud using Pulumi.

> **⚠️ EDUCATIONAL PURPOSE ONLY**
>
> This repository is designed for learning and demonstration purposes. It is **not production-ready** and requires additional hardening and configuration for production use. See [Production Considerations](#production-considerations) for what would need to be added.

## Prerequisites

1. Install talosctl CLI
2. Install kubectl
3. Install Pulumi

## Setup

1. **Create a secret for Hetzner Cloud in Pulumi**
   ```bash
   pulumi config set hcloud:token YOUR_HETZNER_TOKEN --secret
   ```

2. **Create an SSH key** (used for potential rescue mode operations)
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_hetzner_pulumi -C "YOUR_EMAIL"
   ```

## Configuration

The cluster is configured via `src/config.py`. Key settings:

```python
worker_node_count: int = 0  # Number of worker nodes (default: 0)
worker_server_type: str = "cpx22"  # Hetzner server type for workers
controlplane_server_type: str = "cpx22"  # Hetzner server type for control plane
```

**Examples:**

- Single-node (control plane only): `worker_node_count = 0` (default)
- Small cluster: `worker_node_count = 2`
- Production-like: `worker_node_count = 3` with larger server types

## Deployment

Deploy the Talos cluster:
```bash
pulumi up
```

The deployment will:
1. Create Hetzner Cloud server(s) with official Talos ISO (122630)
   - 1 control plane node
   - N worker nodes (configurable, default: 0)
2. Boot Talos Linux 1.11.2 from ISO on all nodes
3. Generate secrets and apply machine configuration to all nodes
4. Install Talos to disk and bootstrap Kubernetes on control plane
5. Save talosconfig to `~/.talos/config` (includes all node IPs)
6. Save kubeconfig to `~/.kube/config-talos`

## Accessing the Cluster

### Using Makefile shortcuts (recommended)

```bash
make health           # Check cluster health
make kubeconfig       # Export kubeconfig
make talos-dashboard  # Open Talos dashboard (control plane)
```

### Using talosctl

```bash
export TALOSCONFIG=~/.talos/config

# Check cluster health
talosctl --nodes $(pulumi stack output control_plane_ip) --endpoints $(pulumi stack output control_plane_ip) health

# Open Talos dashboard (control plane)
talosctl --nodes $(pulumi stack output control_plane_ip) --endpoints $(pulumi stack output control_plane_ip) dashboard

# View logs from control plane
talosctl --nodes $(pulumi stack output control_plane_ip) --endpoints $(pulumi stack output control_plane_ip) logs

# View logs from a specific worker node
WORKER_IP=$(pulumi stack output worker_ips --json | jq -r '.[0]')
talosctl --nodes $WORKER_IP --endpoints $(pulumi stack output control_plane_ip) logs
```

### Using kubectl

```bash
export KUBECONFIG=~/.kube/config-talos

# Check cluster info
kubectl cluster-info

# Get nodes (shows control plane + workers)
kubectl get nodes

# Get all pods
kubectl get pods -A
```

### Upgrade Talos

Upgrade control plane node:

```bash
talosctl --nodes $(pulumi stack output control_plane_ip) --endpoints $(pulumi stack output control_plane_ip) upgrade \
  --image ghcr.io/siderolabs/installer:v1.11.2
```

Upgrade worker nodes individually:

```bash
# For each worker node
for WORKER_IP in $(pulumi stack output worker_ips --json | jq -r '.[]'); do
  talosctl --nodes $WORKER_IP --endpoints $(pulumi stack output control_plane_ip) upgrade \
    --image ghcr.io/siderolabs/installer:v1.11.2
done
```

### Upgrade Kubernetes

```bash
talosctl --nodes $(pulumi stack output control_plane_ip) --endpoints $(pulumi stack output control_plane_ip) upgrade-k8s \
  --to 1.31.4
```

## Development

### Linting and type checking

```bash
make lint       # Run linting and type checking
make format     # Apply auto-fixes to linting and formatting
```

## Important Notes

- **No SSH Access:** Talos doesn't support SSH by design. All management is done via the `talosctl` API.
- **Security:** All communication is encrypted by default with mTLS for API access.
- **Multi-node support:** Configure worker nodes via `worker_node_count` in `src/config.py`
- **Control plane scheduling:** With 0 workers, the control plane allows workload scheduling (`allowSchedulingOnControlPlanes: true`)

## Production Considerations

This setup is educational and **not production-ready**. For production use, you would need:

- **Private Networks:** Isolate VMs in Hetzner private networks instead of exposing them publicly
- **Firewall Rules:** Restrict access to only necessary ports
- **High Availability Control Plane:** Multi-control-plane (3+ nodes) with load balancer
- **Monitoring & Backups:** Prometheus/Grafana monitoring and etcd backup strategy
- **Persistent Storage:** Configure persistent storage solution (Hetzner CSI driver, Longhorn, etc.)

## Cleanup

Destroy all resources:
```bash
pulumi destroy
```

## Troubleshooting

### Server not ready for configuration
If `ConfigurationApply` fails with connection timeout, nodes may still be installing Talos. Wait a few minutes and try again.

### Bootstrap timeout
Bootstrap can take 5-10 minutes. Monitor with:
```bash
make health
```

### Kubeconfig not available
If kubeconfig retrieval fails, ensure the API server is responsive:
```bash
talosctl --nodes $(pulumi stack output control_plane_ip) --endpoints $(pulumi stack output control_plane_ip) service kubelet status
```

### Worker nodes not joining
Check worker node status individually:
```bash
# Get first worker IP
WORKER_IP=$(pulumi stack output worker_ips --json | jq -r '.[0]')
talosctl --nodes $WORKER_IP --endpoints $(pulumi stack output control_plane_ip) get members

# Or check logs
talosctl --nodes $WORKER_IP --endpoints $(pulumi stack output control_plane_ip) logs kubelet
```
