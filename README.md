# Talos Linux Kubernetes on Hetzner Cloud with Pulumi

Deploy a single-node Talos Linux Kubernetes cluster on Hetzner Cloud using Pulumi.

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

## Deployment

Deploy the Talos cluster:
```bash
pulumi up
```

The deployment will:
1. Create a Hetzner Cloud server with official Talos ISO (122630)
2. Boot Talos Linux 1.11.2 from ISO
3. Generate secrets and apply machine configuration
4. Install Talos to disk and bootstrap Kubernetes
5. Save talosconfig to `~/.talos/config`
6. Save kubeconfig to `~/.kube/config-talos`

## Accessing the Cluster

### Using talosctl

```bash
export TALOSCONFIG=~/.talos/config

# Check cluster health
talosctl --nodes $(pulumi stack output server_ip) health

# Open Talos dashboard
talosctl --nodes $(pulumi stack output server_ip) dashboard

# View logs
talosctl --nodes $(pulumi stack output server_ip) logs
```

### Using kubectl

```bash
export KUBECONFIG=~/.kube/config-talos

# Check cluster info
kubectl cluster-info

# Get nodes
kubectl get nodes

# Get all pods
kubectl get pods -A
```

### Using Makefile shortcuts

```bash
make health # Check cluster health
make kubeconfig # Export kubeconfig
make talos-dashboard # Open Talos dashboard
```

### Upgrade Talos

```bash
talosctl --nodes $(pulumi stack output server_ip) upgrade \
  --image ghcr.io/siderolabs/installer:v1.9.1
```

### Upgrade Kubernetes

```bash
talosctl --nodes $(pulumi stack output server_ip) upgrade-k8s \
  --to 1.32.1
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
- **Single-node:** This cluster allows scheduling workloads on the control plane node (`allowSchedulingOnControlPlanes: true`).

## Production Considerations

This setup is educational and **not production-ready**. For production use, you would need:

- **Private Networks:** Isolate VMs in Hetzner private networks instead of exposing them publicly
- **Firewall Rules:** Restrict access to only necessary ports
- **High Availability:** Multi-node control plane (3+ nodes) with load balancer
- **Monitoring & Backups:** Prometheus/Grafana monitoring and etcd backup strategy

## Cleanup

Destroy all resources:
```bash
pulumi destroy
```

## Troubleshooting

### Server not ready for configuration
If `ConfigurationApply` fails with connection timeout, the server may still be installing Talos. Wait a few minutes and try again.

### Bootstrap timeout
Bootstrap can take 5-10 minutes. Monitor with:
```bash
talosctl --nodes $(pulumi stack output server_ip) health
```

### Kubeconfig not available
If kubeconfig retrieval fails, ensure the API server is responsive:
```bash
talosctl --nodes $(pulumi stack output server_ip) service kubelet status
```
