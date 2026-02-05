"""Local filesystem operations for cluster configurations."""

import pulumi
import pulumiverse_talos as talos
from pulumi_command import local

from config import ClusterConfig
from kubernetes import KubernetesAccessOutputs


def save_talosconfig(
    config: ClusterConfig,
    talosconfig: pulumi.Output[str],
    secrets: talos.machine.Secrets,
) -> local.Command:
    """Save talosconfig to local filesystem.

    Args:
        config: Cluster configuration
        talosconfig: Talosconfig content
        secrets: Talos machine secrets (for dependency)

    Returns:
        Command resource that saves talosconfig
    """
    talosconfig_path = config.talosconfig_dir / "config"
    return local.Command(
        "save-talosconfig",
        create=pulumi.Output.concat(
            f"mkdir -p {config.talosconfig_dir} && echo '",
            talosconfig,
            f"' > {talosconfig_path}",
        ),
        opts=pulumi.ResourceOptions(depends_on=[secrets]),
    )


def save_kubeconfig(
    config: ClusterConfig,
    kubeconfig: talos.cluster.Kubeconfig,
) -> local.Command:
    """Save kubeconfig to local filesystem.

    Args:
        config: Cluster configuration
        kubeconfig: Kubeconfig resource

    Returns:
        Command resource that saves kubeconfig
    """
    kubeconfig_path = config.kubeconfig_dir / "config-talos"
    return local.Command(
        "save-kubeconfig",
        create=kubeconfig.kubeconfig_raw.apply(
            lambda cfg: (
                f"mkdir -p {config.kubeconfig_dir} && echo '{cfg}' > {kubeconfig_path} && chmod 600 {kubeconfig_path}"
            )
        ),
        opts=pulumi.ResourceOptions(depends_on=[kubeconfig]),
    )


def save_cluster_configs(
    config: ClusterConfig,
    k8s_access: KubernetesAccessOutputs,
    secrets: talos.machine.Secrets,
) -> tuple[local.Command, local.Command]:
    """Save all cluster configurations to local filesystem.

    Args:
        config: Cluster configuration
        k8s_access: Kubernetes access outputs
        secrets: Talos machine secrets

    Returns:
        Tuple of (save_talosconfig, save_kubeconfig) commands
    """
    save_talos = save_talosconfig(config, k8s_access.talosconfig, secrets)
    save_kube = save_kubeconfig(config, k8s_access.kubeconfig)

    return save_talos, save_kube
