"""Kubernetes cluster access configuration."""

from dataclasses import dataclass

import pulumi
import pulumiverse_talos as talos

from config import ClusterConfig


@dataclass
class KubernetesAccessOutputs:
    """Outputs from Kubernetes access setup.

    Attributes:
        kubeconfig: Kubeconfig resource
        talosconfig: Talosconfig as Pulumi Output
    """

    kubeconfig: talos.cluster.Kubeconfig
    talosconfig: pulumi.Output[str]


def retrieve_kubeconfig(
    secrets: talos.machine.Secrets,
    server_ip: pulumi.Output[str],
    bootstrap: talos.machine.Bootstrap,
) -> talos.cluster.Kubeconfig:
    """Retrieve kubeconfig from Talos cluster.

    Args:
        secrets: Talos machine secrets
        server_ip: Server IP address
        bootstrap: Bootstrap resource to depend on

    Returns:
        Kubeconfig resource
    """
    return talos.cluster.Kubeconfig(
        "kubeconfig",
        client_configuration=secrets.client_configuration,
        node=server_ip,
        opts=pulumi.ResourceOptions(depends_on=[bootstrap]),
    )


def generate_talosconfig(
    config: ClusterConfig,
    secrets: talos.machine.Secrets,
    all_node_ips: list[pulumi.Output[str]],
) -> pulumi.Output[str]:
    """Generate Talos client configuration.

    Args:
        config: Cluster configuration
        secrets: Talos machine secrets
        all_node_ips: All node IP addresses (control plane + workers)

    Returns:
        Talosconfig as Pulumi Output
    """

    nodes: pulumi.Output[list[str]] = pulumi.Output.all(*all_node_ips).apply(  # ty: ignore[missing-argument]
        lambda ips: list(ips)  # ty: ignore[invalid-argument-type]
    )
    # Endpoints should only be control plane nodes (first IP in list)
    # to avoid "no request forwarding" errors
    endpoints: pulumi.Output[list[str]] = all_node_ips[0].apply(lambda ip: [ip])  # ty: ignore[missing-argument, invalid-argument-type]

    talosconfig = talos.client.get_configuration_output(
        cluster_name=config.cluster_name,
        client_configuration=talos.client.GetConfigurationClientConfigurationArgs(
            ca_certificate=secrets.client_configuration.ca_certificate,
            client_certificate=secrets.client_configuration.client_certificate,
            client_key=secrets.client_configuration.client_key,
        ),
        nodes=nodes,
        endpoints=endpoints,
    )

    return talosconfig.talos_config


def setup_kubernetes_access(
    config: ClusterConfig,
    secrets: talos.machine.Secrets,
    control_plane_ip: pulumi.Output[str],
    worker_ips: list[pulumi.Output[str]],
    bootstrap: talos.machine.Bootstrap,
) -> KubernetesAccessOutputs:
    """Set up Kubernetes cluster access.

    Args:
        config: Cluster configuration
        secrets: Talos machine secrets
        control_plane_ip: Control plane IP address
        worker_ips: Worker node IP addresses
        bootstrap: Bootstrap resource to depend on

    Returns:
        KubernetesAccessOutputs with kubeconfig and talosconfig
    """
    kubeconfig = retrieve_kubeconfig(secrets, control_plane_ip, bootstrap)

    all_node_ips = [control_plane_ip] + worker_ips
    talosconfig = generate_talosconfig(config, secrets, all_node_ips)

    return KubernetesAccessOutputs(
        kubeconfig=kubeconfig,
        talosconfig=talosconfig,
    )
