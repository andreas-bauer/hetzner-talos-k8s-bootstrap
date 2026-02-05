"""Talos Linux cluster configuration and bootstrap."""

import json
from dataclasses import dataclass

import pulumi
import pulumiverse_talos as talos
from pulumi_command import local

from config import ClusterConfig


@dataclass
class TalosOutputs:
    """Outputs from Talos cluster setup.

    Attributes:
        secrets: Talos machine secrets
        config: Machine configuration
        config_apply: Configuration apply resource
        bootstrap: Bootstrap resource
    """

    secrets: talos.machine.Secrets
    config: pulumi.Output[str]
    config_apply: talos.machine.ConfigurationApply
    bootstrap: talos.machine.Bootstrap


def generate_talos_secrets() -> talos.machine.Secrets:
    """Generate Talos machine secrets.

    Returns:
        Talos machine secrets resource
    """
    return talos.machine.Secrets("talos-secrets")


def create_machine_config_patches(config: ClusterConfig) -> list[str]:
    """Create machine configuration patches for single-node cluster.

    Args:
        config: Cluster configuration

    Returns:
        List of JSON configuration patches
    """
    return [
        json.dumps(
            {
                "machine": {
                    "install": {
                        "disk": config.install_disk,
                        "image": config.installer_image,
                        "bootloader": True,
                        "wipe": False,
                    },
                },
                "cluster": {
                    "allowSchedulingOnControlPlanes": True,
                },
            }
        )
    ]


def _build_cluster_endpoint(ip: str, port: int) -> str:
    """Build cluster endpoint URL.

    Args:
        ip: Server IP address
        port: Kubernetes API port

    Returns:
        Cluster endpoint URL
    """
    return f"https://{ip}:{port}"


def generate_machine_configuration(
    config: ClusterConfig,
    secrets: talos.machine.Secrets,
    server_ip: pulumi.Output[str],
) -> pulumi.Output[str]:
    """Generate Talos machine configuration.

    Args:
        config: Cluster configuration
        secrets: Talos machine secrets
        server_ip: Server IP address

    Returns:
        Machine configuration as Pulumi Output
    """
    config_patches = create_machine_config_patches(config)

    cluster_endpoint: pulumi.Output[str] = server_ip.apply( # ty: ignore[missing-argument, invalid-assignment]
        lambda ip: _build_cluster_endpoint(ip, config.kubernetes_api_port) # ty: ignore[invalid-argument-type]
    ),

    machine_config = talos.machine.get_configuration_output(
        cluster_name=config.cluster_name,
        machine_type="controlplane",
        cluster_endpoint=cluster_endpoint,
        machine_secrets=talos.machine.MachineSecretsArgs(
            certs=secrets.machine_secrets.certs,
            cluster=secrets.machine_secrets.cluster,
            secrets=secrets.machine_secrets.secrets,
            trustdinfo=secrets.machine_secrets.trustdinfo,
        ),
        config_patches=config_patches,
    )

    return machine_config.machine_configuration


def apply_machine_configuration(
    secrets: talos.machine.Secrets,
    machine_configuration: pulumi.Output[str],
    server_ip: pulumi.Output[str],
    wait_dependency: local.Command,
) -> talos.machine.ConfigurationApply:
    """Apply Talos machine configuration to node.

    Args:
        secrets: Talos machine secrets
        machine_configuration: Machine configuration
        server_ip: Server IP address
        wait_dependency: Resource to wait for before applying

    Returns:
        Configuration apply resource
    """
    return talos.machine.ConfigurationApply(
        "talos-config",
        client_configuration=secrets.client_configuration,
        machine_configuration_input=machine_configuration,
        node=server_ip,
        opts=pulumi.ResourceOptions(depends_on=[wait_dependency]),
    )


def bootstrap_cluster(
    secrets: talos.machine.Secrets,
    server_ip: pulumi.Output[str],
    config_apply: talos.machine.ConfigurationApply,
) -> talos.machine.Bootstrap:
    """Bootstrap Talos Kubernetes cluster.

    Args:
        secrets: Talos machine secrets
        server_ip: Server IP address
        config_apply: Configuration apply resource to depend on

    Returns:
        Bootstrap resource
    """
    return talos.machine.Bootstrap(
        "talos-bootstrap",
        node=server_ip,
        client_configuration=secrets.client_configuration,
        opts=pulumi.ResourceOptions(depends_on=[config_apply]),
    )


def setup_talos_cluster(
    config: ClusterConfig,
    server_ip: pulumi.Output[str],
    wait_dependency: local.Command,
) -> TalosOutputs:
    """Set up complete Talos cluster.

    Args:
        config: Cluster configuration
        server_ip: Server IP address
        wait_dependency: Resource to wait for before setup

    Returns:
        TalosOutputs with all Talos resources
    """
    secrets = generate_talos_secrets()
    machine_config = generate_machine_configuration(config, secrets, server_ip)
    config_apply = apply_machine_configuration(
        secrets, machine_config, server_ip, wait_dependency
    )
    bootstrap = bootstrap_cluster(secrets, server_ip, config_apply)

    return TalosOutputs(
        secrets=secrets,
        config=machine_config,
        config_apply=config_apply,
        bootstrap=bootstrap,
    )
