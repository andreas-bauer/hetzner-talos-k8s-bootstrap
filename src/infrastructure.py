"""Hetzner Cloud infrastructure provisioning."""

from dataclasses import dataclass

import pulumi
import pulumi_hcloud as hcloud
from pulumi_command import local

from config import ClusterConfig, ControlPlaneNodeSpec, NodeSpec, WorkerNodeSpec


@dataclass
class InfrastructureOutputs:
    """Outputs from infrastructure provisioning.

    Attributes:
        ssh_key: Hetzner SSH key resource
        node_servers: Map of node name to server resource
        node_waits: Map of node name to wait command
        control_plane_nodes: List of control plane node specifications
        worker_nodes: List of worker node specifications
    """

    ssh_key: hcloud.SshKey
    node_servers: dict[str, hcloud.Server]
    node_waits: dict[str, local.Command]
    control_plane_nodes: list[ControlPlaneNodeSpec]
    worker_nodes: list[WorkerNodeSpec]


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


def create_server(
    node_spec: NodeSpec,
    ssh_key: hcloud.SshKey,
    config: ClusterConfig,
) -> hcloud.Server:
    """Provision Hetzner server with Talos ISO.

    Args:
        node_spec: Node specification with server configuration
        ssh_key: Hetzner SSH key resource
        config: Cluster configuration

    Returns:
        Hetzner server resource
    """
    return hcloud.Server(
        f"talos-{node_spec.name}",
        name=f"pulumi-talos-k8s-{node_spec.name}",
        server_type=node_spec.server_type,
        location=node_spec.location,
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

    node_servers = {}
    node_waits = {}

    for node_spec in config.all_nodes:
        server = create_server(node_spec, ssh_key, config)
        node_servers[node_spec.name] = server

        wait_cmd = wait_for_talos_api(
            server, config.talos_api_port, f"wait-for-{node_spec.name}"
        )
        node_waits[node_spec.name] = wait_cmd

    return InfrastructureOutputs(
        ssh_key=ssh_key,
        node_servers=node_servers,
        node_waits=node_waits,
        control_plane_nodes=config.control_plane_nodes,
        worker_nodes=config.worker_nodes,
    )
