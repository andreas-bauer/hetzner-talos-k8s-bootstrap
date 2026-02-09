"""Cluster deployment orchestration."""

import pulumi

from config import (
    ClusterConfig,
    ControlPlaneNodeSpec,
    WorkerNodeSpec,
    load_ssh_public_key,
)
from infrastructure import InfrastructureOutputs, provision_infrastructure
from kubernetes import KubernetesAccessOutputs, setup_kubernetes_access
from local_files import save_cluster_configs
from talos_cluster import setup_talos_cluster


class ClusterDeployer:
    """Orchestrates deployment of a Talos Kubernetes cluster.

    Handles infrastructure provisioning, Talos configuration, Kubernetes access
    setup, and Pulumi output exports.
    """

    def __init__(self, config: ClusterConfig) -> None:
        """Initialize deployer with cluster configuration.

        Args:
            config: Cluster configuration to deploy
        """
        self.config = config

    def deploy(self) -> None:
        """Deploy the cluster and export all outputs."""
        ssh_public_key = load_ssh_public_key(self.config.ssh_key_path)

        infra = provision_infrastructure(self.config, ssh_public_key)

        cp_nodes = infra.control_plane_nodes
        control_plane_ip = infra.node_servers[cp_nodes[0].name].ipv4_address
        worker_ips = [
            infra.node_servers[w.name].ipv4_address for w in infra.worker_nodes
        ]
        control_plane_wait = infra.node_waits[cp_nodes[0].name]
        worker_waits = [infra.node_waits[w.name] for w in infra.worker_nodes]

        talos = setup_talos_cluster(
            self.config,
            control_plane_ip,
            worker_ips,
            control_plane_wait,
            worker_waits,
            cp_nodes[0],
            infra.worker_nodes,
        )

        k8s_access = setup_kubernetes_access(
            self.config, talos.secrets, control_plane_ip, worker_ips, talos.bootstrap
        )

        save_cluster_configs(self.config, k8s_access, talos.secrets)

        self._export_outputs(infra, control_plane_ip, worker_ips, k8s_access)

    def _export_outputs(
        self,
        infra: InfrastructureOutputs,
        control_plane_ip: pulumi.Output[str],
        worker_ips: list[pulumi.Output[str]],
        k8s_access: KubernetesAccessOutputs,
    ) -> None:
        """Export all Pulumi stack outputs.

        Args:
            infra: Infrastructure outputs
            control_plane_ip: Control plane IP address
            worker_ips: List of worker IP addresses
            k8s_access: Kubernetes access configuration
        """
        cp_nodes = infra.control_plane_nodes

        pulumi.export(
            "control_plane_server_id", infra.node_servers[cp_nodes[0].name].id
        )
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
            control_plane_ip.apply(  # ty: ignore[missing-argument]
                lambda ip: f"https://{ip}:{self.config.kubernetes_api_port}"  # ty: ignore[invalid-argument-type]
            ),
        )

        pulumi.export("talosconfig", k8s_access.talosconfig)
        pulumi.export("kubeconfig", k8s_access.kubeconfig.kubeconfig_raw)

        all_ips = [control_plane_ip] + worker_ips
        pulumi.export(
            "all_nodes",
            pulumi.Output.all(*all_ips).apply(self._build_nodes_list),  # ty: ignore[missing-argument, invalid-argument-type]
        )

        pulumi.export(
            "node_specs",
            [self._format_node_spec(node) for node in self.config.all_nodes],
        )

    @staticmethod
    def _build_nodes_list(ips: list[str]) -> str:
        """Build comma-separated list of node IPs.

        Args:
            ips: List of node IP addresses

        Returns:
            Comma-separated IP list
        """
        return ",".join(ips)

    def _format_node_spec(
        self, node_spec: ControlPlaneNodeSpec | WorkerNodeSpec
    ) -> dict:
        """Format node spec for export.

        Args:
            node_spec: Node specification to format

        Returns:
            Dict representation of node spec
        """
        spec = {
            "name": f"{self.config.cluster_name}-{node_spec.name}",
            "type": "controlplane"
            if isinstance(node_spec, ControlPlaneNodeSpec)
            else "worker",
            "server_type": node_spec.server_type,
            "location": node_spec.location,
            "labels": dict(node_spec.labels) if node_spec.labels else {},
            "taints": (
                [{"key": t.key, "value": t.value, "effect": t.effect} for t in node_spec.taints]
                if node_spec.taints
                else []
            ),
        }
        if isinstance(node_spec, ControlPlaneNodeSpec):
            spec["allow_scheduling"] = node_spec.allow_scheduling
        return spec
