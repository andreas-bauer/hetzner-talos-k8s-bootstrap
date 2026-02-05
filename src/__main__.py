"""A Python Pulumi program to deploy Talos Linux on Hetzner Cloud."""

import pulumi

from config import (
    ControlPlaneNodeSpec,
    WorkerNodeSpec,
    get_cluster_config,
    load_ssh_public_key,
)
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
    return ",".join(ips)


def _format_node_spec(node_spec: ControlPlaneNodeSpec | WorkerNodeSpec) -> dict:
    """Format node spec for export.

    Args:
        node_spec: Node specification to format

    Returns:
        Dict representation of node spec
    """
    spec = {
        "name": f"pulumi-talos-k8s-{node_spec.name}",
        "type": "controlplane"
        if isinstance(node_spec, ControlPlaneNodeSpec)
        else "worker",
        "server_type": node_spec.server_type,
        "location": node_spec.location,
        "labels": node_spec.labels or {},
        "taints": node_spec.taints or [],
    }
    if isinstance(node_spec, ControlPlaneNodeSpec):
        spec["allow_scheduling"] = node_spec.allow_scheduling
    return spec


def main() -> None:
    """Deploy Talos Kubernetes cluster on Hetzner Cloud."""
    config = get_cluster_config()
    ssh_public_key = load_ssh_public_key(config.ssh_key_path)

    infra = provision_infrastructure(config, ssh_public_key)

    cp_nodes = infra.control_plane_nodes
    control_plane_ip = infra.node_servers[cp_nodes[0].name].ipv4_address

    worker_ips = [infra.node_servers[w.name].ipv4_address for w in infra.worker_nodes]

    control_plane_wait = infra.node_waits[cp_nodes[0].name]
    worker_waits = [infra.node_waits[w.name] for w in infra.worker_nodes]

    talos = setup_talos_cluster(
        config,
        control_plane_ip,
        worker_ips,
        control_plane_wait,
        worker_waits,
        cp_nodes[0],
        infra.worker_nodes,
    )

    k8s_access = setup_kubernetes_access(
        config, talos.secrets, control_plane_ip, worker_ips, talos.bootstrap
    )

    save_cluster_configs(config, k8s_access, talos.secrets)

    pulumi.export("control_plane_server_id", infra.node_servers[cp_nodes[0].name].id)
    pulumi.export("control_plane_ip", control_plane_ip)
    pulumi.export("worker_count", len(infra.worker_nodes))

    if len(infra.worker_nodes) > 0:
        pulumi.export(
            "worker_server_ids",
            [infra.node_servers[w.name].id for w in infra.worker_nodes],
        )
        pulumi.export("worker_ips", worker_ips)

    pulumi.export(
        "cluster_endpoint",
        control_plane_ip.apply(lambda ip: f"https://{ip}:{config.kubernetes_api_port}"),
    )
    pulumi.export("talosconfig", k8s_access.talosconfig)
    pulumi.export("kubeconfig", k8s_access.kubeconfig.kubeconfig_raw)

    all_ips = [control_plane_ip] + worker_ips
    pulumi.export(
        "all_nodes",
        pulumi.Output.all(*all_ips).apply(_build_nodes_list),  # ty: ignore[missing-argument, invalid-argument-type]
    )

    pulumi.export("node_specs", [_format_node_spec(node) for node in config.all_nodes])


if __name__ == "__main__":
    main()
