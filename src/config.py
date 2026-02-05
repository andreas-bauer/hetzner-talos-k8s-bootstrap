"""Configuration management for the Talos Kubernetes cluster."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClusterConfig:
    """Configuration for the Talos Kubernetes cluster.

    Attributes:
        cluster_name: Name of the Kubernetes cluster
        controlplane_server_type: Hetzner server type for control plane (e.g., 'cpx22')
        worker_node_count: Number of worker nodes to create (default: 0)
        worker_server_type: Hetzner server type for workers (e.g., 'cpx22')
        location: Hetzner datacenter location (e.g., 'nbg1')
        talos_iso_id: Hetzner ISO ID for Talos Linux
        talos_version: Talos Linux version
        installer_image: Talos installer image
        install_disk: Disk to install Talos on
        talos_api_port: Port for Talos API
        kubernetes_api_port: Port for Kubernetes API
        ssh_key_path: Path to SSH public key
        talosconfig_dir: Directory for talosconfig file
        kubeconfig_dir: Directory for kubeconfig file
    """

    cluster_name: str = "hetzner-k8s"
    controlplane_server_type: str = "cpx22"
    worker_node_count: int = 2
    worker_server_type: str = "cpx22"
    location: str = "nbg1"
    talos_iso_id: str = (
        "122630"  # Talos Linux 1.11.2 (x86/amd64 with Hetzner + qemu-guest-agent)
    )
    talos_version: str = "v1.11.2"
    installer_image: str = "ghcr.io/siderolabs/installer:v1.11.2"
    install_disk: str = "/dev/sda"
    talos_api_port: int = 50000
    kubernetes_api_port: int = 6443
    ssh_key_path: Path = Path.home() / ".ssh" / "id_ed25519_hetzner_pulumi.pub"
    talosconfig_dir: Path = Path.home() / ".talos"
    kubeconfig_dir: Path = Path.home() / ".kube"


def get_cluster_config() -> ClusterConfig:
    """Get the cluster configuration.

    Returns:
        ClusterConfig instance with default values
    """
    return ClusterConfig()


def load_ssh_public_key(ssh_key_path: Path) -> str:
    """Load SSH public key from file.

    Args:
        ssh_key_path: Path to SSH public key file

    Returns:
        SSH public key as string

    Raises:
        FileNotFoundError: If SSH key file does not exist
    """
    try:
        return ssh_key_path.read_text().strip()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"SSH public key not found at {ssh_key_path}. "
            f"Generate it with: ssh-keygen -t ed25519 -f {ssh_key_path.with_suffix('')}"
        )
