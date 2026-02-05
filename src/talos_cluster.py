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
        control_plane_config: Control plane machine configuration
        worker_configs: Worker machine configurations
        control_plane_apply: Control plane configuration apply resource
        worker_applies: Worker configuration apply resources
        bootstrap: Bootstrap resource
    """

    secrets: talos.machine.Secrets
    control_plane_config: pulumi.Output[str]
    worker_configs: list[pulumi.Output[str]]
    control_plane_apply: talos.machine.ConfigurationApply
    worker_applies: list[talos.machine.ConfigurationApply]
    bootstrap: talos.machine.Bootstrap


def generate_talos_secrets() -> talos.machine.Secrets:
    """Generate Talos machine secrets.

    Returns:
        Talos machine secrets resource
    """
    return talos.machine.Secrets("talos-secrets")


def create_machine_config_patches(
    config: ClusterConfig, machine_type: str
) -> list[str]:
    """Create machine configuration patches.

    Args:
        config: Cluster configuration
        machine_type: Type of machine ('controlplane' or 'worker')

    Returns:
        List of JSON configuration patches
    """
    patch = {
        "machine": {
            "install": {
                "disk": config.install_disk,
                "image": config.installer_image,
                "bootloader": True,
                "wipe": False,
            },
        },
    }

    # Only control plane needs allowSchedulingOnControlPlanes
    if machine_type == "controlplane":
        patch["cluster"] = {
            "allowSchedulingOnControlPlanes": True,
        }

    return [json.dumps(patch)]


def _build_cluster_endpoint(ip: str, port: int) -> str:
    """Build cluster endpoint URL.

    Args:
        ip: Server IP address
        port: Kubernetes API port

    Returns:
        Cluster endpoint URL
    """
    return f"https://{ip}:{port}"


def generate_control_plane_configuration(
    config: ClusterConfig,
    secrets: talos.machine.Secrets,
    control_plane_ip: pulumi.Output[str],
) -> pulumi.Output[str]:
    """Generate Talos control plane machine configuration.

    Args:
        config: Cluster configuration
        secrets: Talos machine secrets
        control_plane_ip: Control plane IP address

    Returns:
        Machine configuration as Pulumi Output
    """
    config_patches = create_machine_config_patches(config, "controlplane")

    cluster_endpoint: pulumi.Output[str] = control_plane_ip.apply( # ty: ignore[missing-argument]
        lambda ip: _build_cluster_endpoint(ip, config.kubernetes_api_port) # ty: ignore[invalid-argument-type]
    )

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


def generate_worker_configuration(
    config: ClusterConfig,
    secrets: talos.machine.Secrets,
    control_plane_ip: pulumi.Output[str],
    worker_index: int,
) -> pulumi.Output[str]:
    """Generate Talos worker machine configuration.

    Args:
        config: Cluster configuration
        secrets: Talos machine secrets
        control_plane_ip: Control plane IP address
        worker_index: Worker node index (0-based)

    Returns:
        Machine configuration as Pulumi Output
    """
    config_patches = create_machine_config_patches(config, "worker")

    # Workers connect to control plane for cluster endpoint
    cluster_endpoint: pulumi.Output[str] = control_plane_ip.apply( # ty: ignore[missing-argument]
        lambda ip: _build_cluster_endpoint(ip, config.kubernetes_api_port) # ty: ignore[invalid-argument-type]
    )

    machine_config = talos.machine.get_configuration_output(
        cluster_name=config.cluster_name,
        machine_type="worker",
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


def apply_configuration_to_node(
    secrets: talos.machine.Secrets,
    machine_configuration: pulumi.Output[str],
    node_ip: pulumi.Output[str],
    wait_dependency: local.Command,
    resource_name: str,
) -> talos.machine.ConfigurationApply:
    """Apply Talos machine configuration to node.

    Args:
        secrets: Talos machine secrets
        machine_configuration: Machine configuration
        node_ip: Node IP address
        wait_dependency: Resource to wait for before applying
        resource_name: Unique name for the configuration apply resource

    Returns:
        Configuration apply resource
    """
    return talos.machine.ConfigurationApply(
        resource_name,
        client_configuration=secrets.client_configuration,
        machine_configuration_input=machine_configuration,
        node=node_ip,
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
    control_plane_ip: pulumi.Output[str],
    worker_ips: list[pulumi.Output[str]],
    control_plane_wait: local.Command,
    worker_waits: list[local.Command],
) -> TalosOutputs:
    """Set up complete Talos cluster.

    Args:
        config: Cluster configuration
        control_plane_ip: Control plane IP address
        worker_ips: Worker node IP addresses
        control_plane_wait: Resource to wait for control plane before setup
        worker_waits: Resources to wait for workers before setup

    Returns:
        TalosOutputs with all Talos resources
    """
    secrets = generate_talos_secrets()

    control_plane_config = generate_control_plane_configuration(
        config, secrets, control_plane_ip
    )
    control_plane_apply = apply_configuration_to_node(
        secrets,
        control_plane_config,
        control_plane_ip,
        control_plane_wait,
        "talos-config-control-plane",
    )

    worker_configs = []
    worker_applies = []
    for i, (worker_ip, worker_wait) in enumerate(zip(worker_ips, worker_waits)):
        worker_config = generate_worker_configuration(
            config, secrets, control_plane_ip, i
        )
        worker_configs.append(worker_config)

        worker_apply = apply_configuration_to_node(
            secrets,
            worker_config,
            worker_ip,
            worker_wait,
            f"talos-config-worker-{i}",
        )
        worker_applies.append(worker_apply)

    # Bootstrap only on control plane, after all configs applied
    all_applies = [control_plane_apply] + worker_applies
    bootstrap = talos.machine.Bootstrap(
        "talos-bootstrap",
        node=control_plane_ip,
        client_configuration=secrets.client_configuration,
        opts=pulumi.ResourceOptions(depends_on=all_applies),
    )

    return TalosOutputs(
        secrets=secrets,
        control_plane_config=control_plane_config,
        worker_configs=worker_configs,
        control_plane_apply=control_plane_apply,
        worker_applies=worker_applies,
        bootstrap=bootstrap,
    )
