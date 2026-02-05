"""Hetzner Cloud infrastructure provisioning."""

from dataclasses import dataclass

import pulumi
import pulumi_hcloud as hcloud
from pulumi_command import local

from config import ClusterConfig


@dataclass
class InfrastructureOutputs:
    """Outputs from infrastructure provisioning.

    Attributes:
        ssh_key: Hetzner SSH key resource
        control_plane_server: Hetzner control plane server resource
        worker_servers: List of Hetzner worker server resources
        control_plane_wait: Command that waits for control plane Talos API readiness
        worker_waits: List of commands that wait for worker Talos API readiness
    """

    ssh_key: hcloud.SshKey
    control_plane_server: hcloud.Server
    worker_servers: list[hcloud.Server]
    control_plane_wait: local.Command
    worker_waits: list[local.Command]


def create_ssh_key(ssh_public_key: str) -> hcloud.SshKey:
    """Create Hetzner SSH key resource.

    Args:
        ssh_public_key: SSH public key content

    Returns:
        Hetzner SSH key resource
    """
    return hcloud.SshKey(
        "hetzner-pulumi-key",
        name="pulumi-talos-ssh-key",
        public_key=ssh_public_key,
    )


def create_control_plane_server(
    config: ClusterConfig, ssh_key: hcloud.SshKey
) -> hcloud.Server:
    """Provision Hetzner control plane server with Talos ISO.

    Args:
        config: Cluster configuration
        ssh_key: Hetzner SSH key resource

    Returns:
        Hetzner control plane server resource
    """
    return hcloud.Server(
        "talos-control-plane-server",
        name="pulumi-talos-k8s-cp-0",
        server_type=config.controlplane_server_type,
        location=config.location,
        ssh_keys=[ssh_key.id],
        image="ubuntu-24.04",  # Required by Hetzner, but will boot from ISO
        iso=config.talos_iso_id,
        public_nets=[
            hcloud.ServerPublicNetArgs(
                ipv4_enabled=True,
                ipv6_enabled=True,
            )
        ],
    )


def create_worker_server(
    config: ClusterConfig, ssh_key: hcloud.SshKey, index: int
) -> hcloud.Server:
    """Provision Hetzner worker server with Talos ISO.

    Args:
        config: Cluster configuration
        ssh_key: Hetzner SSH key resource
        index: Worker node index (0-based)

    Returns:
        Hetzner worker server resource
    """
    return hcloud.Server(
        f"talos-worker-server-{index}",
        name=f"pulumi-talos-k8s-worker-{index}",
        server_type=config.worker_server_type,
        location=config.location,
        ssh_keys=[ssh_key.id],
        image="ubuntu-24.04",  # Required by Hetzner, but will boot from ISO
        iso=config.talos_iso_id,
        public_nets=[
            hcloud.ServerPublicNetArgs(
                ipv4_enabled=True,
                ipv6_enabled=True,
            )
        ],
    )


def wait_for_talos_api(server: hcloud.Server, talos_api_port: int, resource_name: str) -> local.Command:
    """Wait for Talos API to become ready.

    Args:
        server: Hetzner server resource
        talos_api_port: Port for Talos API
        resource_name: Unique name for the wait command resource

    Returns:
        Command resource that waits for Talos API
    """
    return local.Command(
        resource_name,
        create=server.ipv4_address.apply(
            lambda ip: (
                f"echo 'Waiting for Talos API...' && until nc -zv {ip} {talos_api_port} 2>/dev/null; do sleep 5; done && echo 'Talos API ready'"
            )
        ),
        opts=pulumi.ResourceOptions(depends_on=[server]),
    )


def provision_infrastructure(
    config: ClusterConfig, ssh_public_key: str
) -> InfrastructureOutputs:
    """Provision all Hetzner Cloud infrastructure.

    Args:
        config: Cluster configuration
        ssh_public_key: SSH public key content

    Returns:
        InfrastructureOutputs with all provisioned resources
    """
    ssh_key = create_ssh_key(ssh_public_key)

    control_plane_server = create_control_plane_server(config, ssh_key)
    control_plane_wait = wait_for_talos_api(
        control_plane_server, config.talos_api_port, "wait-for-control-plane"
    )

    worker_servers = []
    worker_waits = []
    for i in range(config.worker_node_count):
        worker = create_worker_server(config, ssh_key, i)
        worker_servers.append(worker)
        worker_wait = wait_for_talos_api(
            worker, config.talos_api_port, f"wait-for-worker-{i}"
        )
        worker_waits.append(worker_wait)

    return InfrastructureOutputs(
        ssh_key=ssh_key,
        control_plane_server=control_plane_server,
        worker_servers=worker_servers,
        control_plane_wait=control_plane_wait,
        worker_waits=worker_waits,
    )
