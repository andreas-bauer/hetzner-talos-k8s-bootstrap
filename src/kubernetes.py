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
    server_ip: pulumi.Output[str],
) -> pulumi.Output[str]:
    """Generate Talos client configuration.

    Args:
        config: Cluster configuration
        secrets: Talos machine secrets
        server_ip: Server IP address

    Returns:
        Talosconfig as Pulumi Output
    """
    nodes: pulumi.Output[list[str]] = server_ip.apply(lambda ip: [ip]) # ty: ignore[invalid-argument-type, missing-argument]
    endpoints: pulumi.Output[list[str]] = server_ip.apply(lambda ip: [ip]) # ty: ignore[invalid-argument-type, missing-argument]

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
    server_ip: pulumi.Output[str],
    bootstrap: talos.machine.Bootstrap,
) -> KubernetesAccessOutputs:
    """Set up Kubernetes cluster access.

    Args:
        config: Cluster configuration
        secrets: Talos machine secrets
        server_ip: Server IP address
        bootstrap: Bootstrap resource to depend on

    Returns:
        KubernetesAccessOutputs with kubeconfig and talosconfig
    """
    kubeconfig = retrieve_kubeconfig(secrets, server_ip, bootstrap)
    talosconfig = generate_talosconfig(config, secrets, server_ip)

    return KubernetesAccessOutputs(
        kubeconfig=kubeconfig,
        talosconfig=talosconfig,
    )
