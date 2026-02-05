"""A Python Pulumi program to deploy Talos Linux on Hetzner Cloud."""

import pulumi

from config import get_cluster_config, load_ssh_public_key
from infrastructure import provision_infrastructure
from kubernetes import setup_kubernetes_access
from local_files import save_cluster_configs
from talos_cluster import setup_talos_cluster


def _build_nodes_list(ips: list[str]) -> str:
    """Build comma-separated list of node IPs.

    Args:
        ips: List of node IP addresses

    Returns:
        Comma-separated IP list
    """
    return ','.join(ips)


def main() -> None:
    """Deploy Talos Kubernetes cluster on Hetzner Cloud."""
    config = get_cluster_config()
    ssh_public_key = load_ssh_public_key(config.ssh_key_path)

    infra = provision_infrastructure(config, ssh_public_key)

    control_plane_ip = infra.control_plane_server.ipv4_address
    worker_ips = [worker.ipv4_address for worker in infra.worker_servers]

    talos = setup_talos_cluster(
        config,
        control_plane_ip,
        worker_ips,
        infra.control_plane_wait,
        infra.worker_waits,
    )

    k8s_access = setup_kubernetes_access(
        config, talos.secrets, control_plane_ip, worker_ips, talos.bootstrap
    )

    save_cluster_configs(config, k8s_access, talos.secrets)

    pulumi.export("control_plane_server_id", infra.control_plane_server.id)
    pulumi.export("control_plane_ip", control_plane_ip)
    pulumi.export("worker_count", config.worker_node_count)

    if config.worker_node_count > 0:
        pulumi.export("worker_server_ids", [w.id for w in infra.worker_servers])
        pulumi.export("worker_ips", worker_ips)

    pulumi.export(
        "cluster_endpoint",
        control_plane_ip.apply(
            lambda ip: f"https://{ip}:{config.kubernetes_api_port}"
        ),
    )
    pulumi.export("talosconfig", k8s_access.talosconfig)
    pulumi.export("kubeconfig", k8s_access.kubeconfig.kubeconfig_raw)

    all_ips = [control_plane_ip] + worker_ips
    pulumi.export(
        "all_nodes",
        pulumi.Output.all(*all_ips).apply(_build_nodes_list), # ty: ignore[missing-argument, invalid-argument-type]
    )


if __name__ == "__main__":
    main()
