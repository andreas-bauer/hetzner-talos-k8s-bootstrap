"""A Python Pulumi program to deploy Talos Linux on Hetzner Cloud."""

from config import ClusterConfigBuilder
from deployer import ClusterDeployer


def main() -> None:
    """Deploy Talos Kubernetes cluster on Hetzner Cloud."""
    config = (
        ClusterConfigBuilder()
        .with_cluster_name("hetzner-k8s")
        .add_control_plane(
            name="cp-0", location="nbg1", server_type="cx33", allow_scheduling=False
        )
        .add_worker(name="worker-1", location="nbg1", server_type="cx33")
        .add_worker(name="worker-0", location="nbg1", server_type="cx33")
        .build()
    )

    deployer = ClusterDeployer(config)
    deployer.deploy()


if __name__ == "__main__":
    main()
