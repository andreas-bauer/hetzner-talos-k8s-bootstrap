"""A Python Pulumi program to deploy Talos Linux on Hetzner Cloud."""

import json
from pathlib import Path

import pulumi
import pulumi_hcloud as hcloud
import pulumiverse_talos as talos
from pulumi_command import local

ssh_key_path = Path.home() / ".ssh" / "id_ed25519_hetzner_pulumi.pub"
try:
    ssh_public_key = ssh_key_path.read_text().strip()
except FileNotFoundError:
    raise FileNotFoundError(
        f"SSH public key not found at {ssh_key_path}. "
        "Generate it with: ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_hetzner_pulumi"
    )

ssh_key = hcloud.SshKey(
    "hetzner-pulumi-key",
    name="pulumi-talos-ssh-key",
    public_key=ssh_public_key,
)

# Provision Hetzner server with official Talos ISO
# ISO 122630 = Talos Linux 1.11.2 (x86/amd64 with Hetzner + qemu-guest-agent)
server = hcloud.Server(
    "talos-server",
    name="pulumi-talos-k8s",
    server_type="cpx22",
    location="nbg1",
    ssh_keys=[ssh_key.id],
    image="ubuntu-24.04",  # Required by Hetzner, but will boot from ISO
    iso="122630",  # Official Talos Linux 1.11.2 ISO
    public_nets=[
        hcloud.ServerPublicNetArgs(
            ipv4_enabled=True,
            ipv6_enabled=True,
        )
    ],
)

wait_for_talos = local.Command(
    "wait-for-talos",
    create=server.ipv4_address.apply(
        lambda ip: f"echo 'Waiting for Talos API...' && until nc -zv {ip} 50000 2>/dev/null; do sleep 5; done && echo 'Talos API ready'"
    ),
    opts=pulumi.ResourceOptions(depends_on=[server]),
)

secrets = talos.machine.Secrets("talos-secrets")

# Create machine configuration patches for single-node cluster
config_patches = [
    json.dumps({
        "machine": {
            "install": {
                "disk": "/dev/sda",
                "image": "ghcr.io/siderolabs/installer:v1.11.2",
                "bootloader": True,
                "wipe": False,
            },
        },
        "cluster": {
            "allowSchedulingOnControlPlanes": True,
        },
    })
]

machine_config = talos.machine.get_configuration_output(
    cluster_name="hetzner-k8s",
    machine_type="controlplane",
    cluster_endpoint=server.ipv4_address.apply(lambda ip: f"https://{ip}:6443"),
    machine_secrets=talos.machine.MachineSecretsArgs(
        certs=secrets.machine_secrets.certs,
        cluster=secrets.machine_secrets.cluster,
        secrets=secrets.machine_secrets.secrets,
        trustdinfo=secrets.machine_secrets.trustdinfo,
    ),
    config_patches=config_patches,
)

config_apply = talos.machine.ConfigurationApply(
    "talos-config",
    client_configuration=secrets.client_configuration,
    machine_configuration_input=machine_config.machine_configuration,
    node=server.ipv4_address,
    opts=pulumi.ResourceOptions(depends_on=[wait_for_talos]),
)

bootstrap = talos.machine.Bootstrap(
    "talos-bootstrap",
    node=server.ipv4_address,
    client_configuration=secrets.client_configuration,
    opts=pulumi.ResourceOptions(depends_on=[config_apply]),
)

kubeconfig = talos.cluster.Kubeconfig(
    "kubeconfig",
    client_configuration=secrets.client_configuration,
    node=server.ipv4_address,
    opts=pulumi.ResourceOptions(depends_on=[bootstrap]),
)

talosconfig = talos.client.get_configuration_output(
    cluster_name="hetzner-k8s",
    client_configuration=talos.client.GetConfigurationClientConfigurationArgs(
        ca_certificate=secrets.client_configuration.ca_certificate,
        client_certificate=secrets.client_configuration.client_certificate,
        client_key=secrets.client_configuration.client_key,
    ),
    nodes=[server.ipv4_address],
    endpoints=[server.ipv4_address],
)

save_talosconfig = local.Command(
    "save-talosconfig",
    create=pulumi.Output.concat(
        "mkdir -p ~/.talos && echo '", talosconfig.talos_config, "' > ~/.talos/config"
    ),
    opts=pulumi.ResourceOptions(depends_on=[secrets]),
)

save_kubeconfig = local.Command(
    "save-kubeconfig",
    create=kubeconfig.kubeconfig_raw.apply(
        lambda cfg: f"mkdir -p ~/.kube && echo '{cfg}' > ~/.kube/config-talos && chmod 600 ~/.kube/config-talos"
    ),
    opts=pulumi.ResourceOptions(depends_on=[kubeconfig]),
)

pulumi.export("server_id", server.id)
pulumi.export("server_ip", server.ipv4_address)
pulumi.export("cluster_endpoint", server.ipv4_address.apply(lambda ip: f"https://{ip}:6443"))
pulumi.export("talosconfig", talosconfig.talos_config)
pulumi.export("kubeconfig", kubeconfig.kubeconfig_raw)
pulumi.export(
    "talosctl_command",
    server.ipv4_address.apply(lambda ip: f"talosctl --nodes {ip} health"),
)
