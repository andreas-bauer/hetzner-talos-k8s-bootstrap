"""A Python Pulumi program to deploy Talos Linux on Hetzner Cloud."""

import pulumi

from config import get_cluster_config, load_ssh_public_key
from infrastructure import provision_infrastructure
from kubernetes import setup_kubernetes_access
from local_files import save_cluster_configs
from talos_cluster import setup_talos_cluster


def main() -> None:
    """Deploy Talos Kubernetes cluster on Hetzner Cloud."""
    config = get_cluster_config()
    ssh_public_key = load_ssh_public_key(config.ssh_key_path)

    infra = provision_infrastructure(config, ssh_public_key)

    talos = setup_talos_cluster(config, infra.server.ipv4_address, infra.wait_command)

    k8s_access = setup_kubernetes_access(
        config, talos.secrets, infra.server.ipv4_address, talos.bootstrap
    )

    save_cluster_configs(config, k8s_access, talos.secrets)

    pulumi.export("server_id", infra.server.id)
    pulumi.export("server_ip", infra.server.ipv4_address)
    pulumi.export(
        "cluster_endpoint",
        infra.server.ipv4_address.apply(
            lambda ip: f"https://{ip}:{config.kubernetes_api_port}"
        ),
    )
    pulumi.export("talosconfig", k8s_access.talosconfig)
    pulumi.export("kubeconfig", k8s_access.kubeconfig.kubeconfig_raw)
    pulumi.export(
        "talosctl_command",
        infra.server.ipv4_address.apply(lambda ip: f"talosctl --nodes {ip} health"),
    )


if __name__ == "__main__":
    main()
