"""Configuration management for the Talos Kubernetes cluster."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class BaseNodeSpec:
    """Base specification for nodes with common attributes.

    Attributes:
        name: Node name (e.g., 'cp-0', 'worker-0', 'worker-1')
        server_type: Hetzner server type (e.g., 'cp33')
        location: Hetzner datacenter location (e.g., 'nbg1')
        labels: Kubernetes node labels
        taints: Kubernetes node taints (list of dicts with keys: key, value, effect)
    """

    name: str
    server_type: str = "cp33"
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


NodeSpec = ControlPlaneNodeSpec | WorkerNodeSpec


@dataclass
class ClusterConfig:
    """Configuration for the Talos Kubernetes cluster."""

    cluster_name: str
    control_plane_nodes: list[ControlPlaneNodeSpec]
    worker_nodes: list[WorkerNodeSpec]
    talos_iso_id: str
    talos_version: str
    installer_image: str
    install_disk: str
    talos_api_port: int
    kubernetes_api_port: int
    ssh_key_path: Path
    talosconfig_dir: Path
    kubeconfig_dir: Path

    @property
    def all_nodes(self) -> list[NodeSpec]:
        """Get all node specifications (control plane + workers)."""
        return list(self.control_plane_nodes) + list(self.worker_nodes)


class ClusterConfigBuilder:
    """Builder for creating ClusterConfig instances with a fluent interface.

    Provides chainable methods for configuring cluster settings and nodes.
    """

    def __init__(self) -> None:
        """Initialize builder with default values."""
        self._cluster_name = "hetzner-k8s"
        self._control_plane_nodes: list[ControlPlaneNodeSpec] = []
        self._worker_nodes: list[WorkerNodeSpec] = []
        self._talos_iso_id = "122630"
        self._talos_version = "v1.11.2"
        self._installer_image = f"ghcr.io/siderolabs/installer:{self._talos_version}"
        self._install_disk = "/dev/sda"
        self._talos_api_port = 50000
        self._kubernetes_api_port = 6443
        self._ssh_key_path = Path.home() / ".ssh" / "id_ed25519_hetzner_pulumi.pub"
        self._talosconfig_dir = Path.home() / ".talos"
        self._kubeconfig_dir = Path.home() / ".kube"

    def with_cluster_name(self, name: str) -> "ClusterConfigBuilder":
        """Set the cluster name.

        Args:
            name: Cluster name

        Returns:
            Self for chaining
        """
        self._cluster_name = name
        return self

    def with_talos_version(self, version: str) -> "ClusterConfigBuilder":
        """Set the Talos version and update installer image.

        Args:
            version: Talos version (e.g., 'v1.11.2')

        Returns:
            Self for chaining
        """
        self._talos_version = version
        self._installer_image = f"ghcr.io/siderolabs/installer:{version}"
        return self

    def with_ssh_key_path(self, path: Path | str) -> "ClusterConfigBuilder":
        """Set the SSH key path.

        Args:
            path: Path to SSH public key file

        Returns:
            Self for chaining
        """
        self._ssh_key_path = Path(path) if isinstance(path, str) else path
        return self

    def with_config_directories(
        self,
        talosconfig_dir: Path | str,
        kubeconfig_dir: Path | str,
    ) -> "ClusterConfigBuilder":
        """Set the output directories for configs.

        Args:
            talosconfig_dir: Directory for talosconfig file
            kubeconfig_dir: Directory for kubeconfig file

        Returns:
            Self for chaining
        """
        self._talosconfig_dir = (
            Path(talosconfig_dir)
            if isinstance(talosconfig_dir, str)
            else talosconfig_dir
        )
        self._kubeconfig_dir = (
            Path(kubeconfig_dir) if isinstance(kubeconfig_dir, str) else kubeconfig_dir
        )
        return self

    def add_control_plane(
        self,
        name: str,
        server_type: str = "cx33",
        location: str = "nbg1",
        allow_scheduling: bool = False,
        labels: dict[str, str] | None = None,
        taints: list[dict[str, str]] | None = None,
    ) -> "ClusterConfigBuilder":
        """Add a control plane node.

        Args:
            name: Node name (e.g., 'cp-0')
            server_type: Hetzner server type
            location: Hetzner datacenter location
            allow_scheduling: Allow pod scheduling on this node
            labels: Kubernetes node labels
            taints: Kubernetes node taints

        Returns:
            Self for chaining
        """

        if len(self._control_plane_nodes) > 0:
            raise ValueError(
                "Currently, only one control plane node is supported iœn this configuration"
            )

        node = ControlPlaneNodeSpec(
            name=name,
            server_type=server_type,
            location=location,
            allow_scheduling=allow_scheduling,
            labels=labels,
            taints=taints,
        )
        self._control_plane_nodes.append(node)
        return self

    def add_worker(
        self,
        name: str,
        server_type: str = "cpx22",
        location: str = "nbg1",
        labels: dict[str, str] | None = None,
        taints: list[dict[str, str]] | None = None,
    ) -> "ClusterConfigBuilder":
        """Add a worker node.

        Args:
            name: Node name (e.g., 'worker-0')
            server_type: Hetzner server type
            location: Hetzner datacenter location
            labels: Kubernetes node labels
            taints: Kubernetes node taints

        Returns:
            Self for chaining
        """
        node = WorkerNodeSpec(
            name=name,
            server_type=server_type,
            location=location,
            labels=labels,
            taints=taints,
        )
        self._worker_nodes.append(node)
        return self

    def build(self) -> ClusterConfig:
        """Build the immutable ClusterConfig.

        Returns:
            ClusterConfig instance

        Raises:
            ValueError: If no control plane nodes are configured
            ValueError: If more than one control plane node is configured (not supported yet)
        """
        if not self._control_plane_nodes:
            raise ValueError("At least one control plane node is required")

        if len(self._control_plane_nodes) > 1:
            raise ValueError(
                "Currently, only one control plane node is supported in this configuration"
            )

        return ClusterConfig(
            cluster_name=self._cluster_name,
            control_plane_nodes=self._control_plane_nodes,
            worker_nodes=self._worker_nodes,
            talos_iso_id=self._talos_iso_id,
            talos_version=self._talos_version,
            installer_image=self._installer_image,
            install_disk=self._install_disk,
            talos_api_port=self._talos_api_port,
            kubernetes_api_port=self._kubernetes_api_port,
            ssh_key_path=self._ssh_key_path,
            talosconfig_dir=self._talosconfig_dir,
            kubeconfig_dir=self._kubeconfig_dir,
        )


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
