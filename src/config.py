"""Configuration management for the Talos Kubernetes cluster."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BaseNodeSpec:
    """Base specification for nodes with common attributes.

    Attributes:
        name: Node name (e.g., 'cp-0', 'worker-0', 'worker-1')
        server_type: Hetzner server type (e.g., 'cpx22')
        location: Hetzner datacenter location (e.g., 'nbg1')
        labels: Kubernetes node labels
        taints: Kubernetes node taints (list of dicts with keys: key, value, effect)
    """

    name: str
    server_type: str = "cpx22"
    location: str = "nbg1"
    labels: dict[str, str] | None = None
    taints: list[dict[str, str]] | None = None


@dataclass
class ControlPlaneNodeSpec(BaseNodeSpec):
    """Specification for a control plane node.

    Attributes:
        allow_scheduling: Allow pod scheduling on control plane
    """

    allow_scheduling: bool = True


@dataclass
class WorkerNodeSpec(BaseNodeSpec):
    """Specification for a worker node."""

    pass


# Type alias for any node
NodeSpec = ControlPlaneNodeSpec | WorkerNodeSpec


@dataclass
class ClusterConfig:
    """Configuration for the Talos Kubernetes cluster.

    Attributes:
        cluster_name: Name of the Kubernetes cluster
        control_plane_nodes: List of control plane node specifications
        worker_nodes: List of worker node specifications
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
    control_plane_nodes: list[ControlPlaneNodeSpec] = field(
        default_factory=lambda: [ControlPlaneNodeSpec(name="cp-0")]
    )
    worker_nodes: list[WorkerNodeSpec] = field(
        default_factory=lambda: [
            WorkerNodeSpec(name="worker-0"),
            WorkerNodeSpec(name="worker-1"),
        ]
    )
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

    @property
    def all_nodes(self) -> list[NodeSpec]:
        """Get all node specifications (control plane + workers)."""
        return list(self.control_plane_nodes) + list(self.worker_nodes)


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
