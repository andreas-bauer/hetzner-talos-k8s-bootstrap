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
        server: Hetzner server resource
        wait_command: Command that waits for Talos API readiness
    """

    ssh_key: hcloud.SshKey
    server: hcloud.Server
    wait_command: local.Command


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


def create_server(config: ClusterConfig, ssh_key: hcloud.SshKey) -> hcloud.Server:
    """Provision Hetzner server with Talos ISO.

    Args:
        config: Cluster configuration
        ssh_key: Hetzner SSH key resource

    Returns:
        Hetzner server resource
    """
    return hcloud.Server(
        "talos-server",
        name="pulumi-talos-k8s",
        server_type=config.server_type,
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


def wait_for_talos_api(server: hcloud.Server, talos_api_port: int) -> local.Command:
    """Wait for Talos API to become ready.

    Args:
        server: Hetzner server resource
        talos_api_port: Port for Talos API

    Returns:
        Command resource that waits for Talos API
    """
    return local.Command(
        "wait-for-talos",
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
    server = create_server(config, ssh_key)
    wait_command = wait_for_talos_api(server, config.talos_api_port)

    return InfrastructureOutputs(
        ssh_key=ssh_key,
        server=server,
        wait_command=wait_command,
    )
