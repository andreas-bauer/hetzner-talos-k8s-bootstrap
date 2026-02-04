.PHONY: lint format health kubeconfig talos-dashboard

lint:
	uv run ruff check
	uv run ty check

format:
	uv run ruff check --fix
	uv run ruff format

health:
	@talosctl --nodes $$(pulumi stack output server_ip) health

kubeconfig:
	@pulumi stack output kubeconfig --show-secrets > ~/.kube/config-talos
	@chmod 600 ~/.kube/config-talos
	@echo "Kubeconfig saved to ~/.kube/config-talos"
	@echo "Run: export KUBECONFIG=~/.kube/config-talos"

talos-dashboard:
	@talosctl --nodes $$(pulumi stack output server_ip) dashboard
