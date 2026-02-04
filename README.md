# Example on how to setup Kubernetes on Hetzner Cloud with Pulumi

## Setup

1. Create a secret for Hetzner cloud on pulumi
```
pulumi config set hcloud:token YOUR_HETZNER_TOKEN --secret
```

2. Create an SSH key
```
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_hetzner_pulumi -C "YOUR_EMAIL"
```

## Usage

### Development

```bash
make lint # Runs linting and type checking
make format # Applies auto-fixes to linting and formatting
```
