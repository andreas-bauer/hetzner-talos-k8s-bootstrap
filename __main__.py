"""A Python Pulumi program to deploy a minimal Hetzner Cloud VM."""

import pulumi
import pulumi_hcloud as hcloud
from pathlib import Path

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
    name="pulumi-demo-ssh-key",
    public_key=ssh_public_key,
)

server = hcloud.Server(
    "demo-server",
    name="pulumi-hetzner-demo",
    server_type="cpx22",
    image="ubuntu-24.04",
    location="nbg1",
    ssh_keys=[ssh_key.id],
)

pulumi.export("server_id", server.id)
pulumi.export("ipv4_address", server.ipv4_address)
pulumi.export("ipv6_address", server.ipv6_address)
pulumi.export("ssh_command", pulumi.Output.concat("ssh -i ~/.ssh/id_ed25519_hetzner_pulumi root@", server.ipv4_address))
