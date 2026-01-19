from typing import Union

from ..exceptions import ConfigurationError, IncusCommandError
from .base import Provisioner


class LLMNR(Provisioner):
    config_key = "llmnr"

    def validate_config(self, instance_name: str, config: Union[bool, dict, str]):
        if not isinstance(config, bool):
            raise ConfigurationError(
                f"Provisioning 'llmnr' step in instance '{instance_name}' must have a boolean value."
            )

    def _install_systemd_resolved(self, instance_name: str):
        """Install systemd-resolved."""
        self.reporter.info("Installing systemd-resolved...")
        try:
            self.incus.exec(instance_name, ["sh", "-c", "command -v apt-get"], capture_output=True)
            self.incus.exec(
                instance_name,
                ["sh", "-c", "apt-get update && apt-get -y install systemd-resolved"],
                capture_output=False,
            )
            return
        except IncusCommandError:
            pass  # apt-get not found, try next package manager

        try:
            self.incus.exec(instance_name, ["sh", "-c", "command -v dnf"], capture_output=True)
            self.incus.exec(
                instance_name, ["sh", "-c", "dnf -y -q install systemd-resolved"], capture_output=False
            )
            return
        except IncusCommandError:
            pass  # dnf not found

        try:
            self.incus.exec(instance_name, ["sh", "-c", "command -v pacman"], capture_output=True)
            self.incus.exec(
                instance_name,
                ["sh", "-c", "pacman -Syu --noconfirm systemd-resolvconf"],
                capture_output=False,
            )
            return
        except IncusCommandError:
            pass  # pacman not found

        self.reporter.warning(
            "Could not install systemd-resolved. No supported package manager (apt-get, dnf, pacman) found."
        )

    def _configure_llmnr(self, instance_name: str):
        """Configure LLMNR in resolved.conf."""
        self.reporter.info("Configuring LLMNR...")
        script = """
mkdir -p /etc/systemd/resolved.conf.d
cat <<EOF > /etc/systemd/resolved.conf.d/llmnr.conf
[Resolve]
LLMNR=yes
EOF
"""
        self.incus.exec(instance_name, ["sh", "-c", script])

    def _restart_systemd_resolved(self, instance_name: str):
        """Restart systemd-resolved service."""
        self.reporter.info("Restarting systemd-resolved...")
        self.incus.exec(instance_name, ["systemctl", "restart", "systemd-resolved"])

    def provision(self, instance_name: str, config: Union[bool, dict, str]) -> None:
        """Enable LLMNR on an instance."""
        if not isinstance(config, bool):
            raise TypeError(f"Config for LLMNR provisioner must be a bool, got {type(config)}")
        if not config:
            return

        self.reporter.success(f"Enabling LLMNR on instance {instance_name}...")
        try:
            self._install_systemd_resolved(instance_name)
            self._configure_llmnr(instance_name)
            self._restart_systemd_resolved(instance_name)
            self.reporter.success(f"LLMNR enabled on {instance_name}.")
        except IncusCommandError as e:
            self.reporter.error(f"Failed to enable LLMNR on {instance_name}: {e}")
