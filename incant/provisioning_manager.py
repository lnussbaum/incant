"""
Provisioning management for Incant.
"""

import glob
import os
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from typing import TypedDict, Union

from .exceptions import IncusCommandError
from .incus_cli import IncusCLI
from .reporter import Reporter
from .types import FilePushConfig, ProvisionSteps


class PackageManager(TypedDict):
    check_cmd: str
    install_cmds: list[str]


class ProvisionManager:
    """Handles provisioning of instances."""

    def __init__(self, incus_cli: IncusCLI, reporter: Reporter):
        self.incus = incus_cli
        self.reporter = reporter

    def provision(self, instance_name: str, provisions: ProvisionSteps):
        """Provision an instance."""
        if provisions:
            self.reporter.success(f"Provisioning instance {instance_name}...")

            # Handle provisioning steps
            if isinstance(provisions, str):
                self.incus.run_script(instance_name, provisions)
            elif isinstance(provisions, list):
                for step in provisions:
                    if isinstance(step, dict) and "copy" in step:
                        step["copy"]["instance_name"] = instance_name
                        self.incus.file_push(FilePushConfig(**step["copy"]))
                    elif isinstance(step, dict) and "ssh" in step:
                        self.ssh_setup(instance_name, step["ssh"])
                    elif isinstance(step, dict) and "llmnr" in step:
                        self.llmnr_setup(instance_name, step["llmnr"])
                    else:
                        self.reporter.info("Running provisioning step ...")
                        self.incus.run_script(instance_name, step)
        else:
            self.reporter.info(f"No provisioning found for {instance_name}.")

    def llmnr_setup(self, instance_name: str, llmnr_config: Union[dict, bool]) -> None:
        """Enable LLMNR on an instance."""
        if not llmnr_config:
            return

        self.reporter.success(f"Enabling LLMNR on instance {instance_name}...")
        try:
            self._install_systemd_resolved(instance_name)
            self._configure_llmnr(instance_name)
            self._restart_systemd_resolved(instance_name)
            self.reporter.success(f"LLMNR enabled on {instance_name}.")
        except IncusCommandError as e:
            self.reporter.error(f"Failed to enable LLMNR on {instance_name}: {e}")

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
                instance_name, ["sh", "-c", "dnf -y install systemd-resolved"], capture_output=False
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

    def clean_known_hosts(self, name: str) -> None:
        """Remove an instance's name from the known_hosts file and add the new host key."""
        self.reporter.success(
            f"Updating {name} in known_hosts to avoid SSH warnings...",
        )
        known_hosts_path = Path.home() / ".ssh" / "known_hosts"
        if known_hosts_path.exists():
            try:
                # Remove existing entry
                subprocess.run(
                    ["ssh-keygen", "-R", name], check=False, capture_output=True
                )  # nosec B603, B607
            except FileNotFoundError as e:
                raise IncusCommandError("ssh-keygen not found, cannot clean known_hosts.") from e

        # Initiate a connection to accept the new host key
        try:
            subprocess.run(  # nosec B603, B607
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=5",
                    name,
                    "exit",  # Just connect and exit
                ],
                check=False,  # Don't raise an error if connection fails (e.g., SSH not ready yet)
                capture_output=True,
            )
        except FileNotFoundError:
            self.reporter.warning(
                "ssh command not found, cannot add new host key to known_hosts.",
            )

    def _install_ssh_server(self, name: str) -> bool:
        """Installs SSH server in the instance."""
        package_managers: list[PackageManager] = [
            {
                "check_cmd": "command -v apt-get",
                "install_cmds": ["apt-get update && apt-get -y install ssh"],
            },
            {
                "check_cmd": "command -v dnf",
                "install_cmds": [
                    "dnf -y install openssh-server",
                    "systemctl enable sshd",
                    "systemctl start sshd",
                ],
            },
            {
                "check_cmd": "command -v pacman",
                "install_cmds": [
                    "pacman -Syu --noconfirm openssh",
                    "systemctl enable sshd",
                    "systemctl start sshd",
                ],
            },
        ]

        for pm in package_managers:
            try:
                self.incus.exec(name, ["sh", "-c", pm["check_cmd"]], capture_output=True)
                for cmd in pm["install_cmds"]:
                    self.incus.exec(name, ["sh", "-c", cmd], capture_output=False)
                return True  # Installed
            except IncusCommandError:
                continue  # Try next package manager
        return False  # Not installed

    def _get_authorized_keys_content(self, ssh_config: Union[dict, bool]) -> str:
        """Determines the content for authorized_keys."""
        source_path_str = ssh_config.get("authorized_keys") if isinstance(ssh_config, dict) else None

        if source_path_str:
            source_path = Path(source_path_str).expanduser()
            if source_path.exists():
                with open(source_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                self.reporter.warning(
                    f"Provided authorized_keys file not found: {source_path}. Skipping copy.",
                )
                return ""
        else:
            # Concatenate all public keys from ~/.ssh/id_*.pub
            ssh_dir = Path.home() / ".ssh"
            pub_keys_content = []
            key_files = glob.glob(os.path.join(ssh_dir, "id_*.pub"))

            for key_file_path in key_files:
                with open(key_file_path, "r", encoding="utf-8") as f:
                    pub_keys_content.append(f.read().strip())

            if pub_keys_content:
                return "\n".join(pub_keys_content) + "\n"
            else:
                self.reporter.warning(
                    "No public keys found in ~/.ssh/id_*.pub and no authorized_keys file provided. "
                    "SSH access might not be possible without a password.",
                )
                return ""

    def _write_authorized_keys(self, name: str, content: str) -> None:
        """Writes the authorized_keys content to the instance."""
        if not content:
            return

        self.reporter.success(f"Filling authorized_keys in {name}...")
        self.incus.exec(name, ["mkdir", "-p", "/root/.ssh"])

        fd, temp_path = tempfile.mkstemp(prefix="incant_authorized_keys_")
        try:
            with os.fdopen(fd, "w") as temp_file:
                temp_file.write(content)

            self.incus.file_push(
                FilePushConfig(
                    instance_name=name,
                    source=temp_path,
                    target="/root/.ssh/authorized_keys",
                    uid=0,
                    gid=0,
                    quiet=True,
                )
            )
        finally:
            os.remove(temp_path)

    def ssh_setup(self, name: str, ssh_config: Union[dict, bool]) -> None:
        """Install SSH server and copy authorized_keys."""
        if isinstance(ssh_config, bool):
            ssh_config = {"clean_known_hosts": True}

        self.reporter.success(f"Installing SSH server in {name}...")
        if not self._install_ssh_server(name):
            self.reporter.error(
                f"Failed to install SSH server in {name}. "
                "No supported package manager (apt-get, dnf, pacman) found.",
            )
            return

        content = self._get_authorized_keys_content(ssh_config)
        self._write_authorized_keys(name, content)

        if ssh_config.get("clean_known_hosts"):
            self.clean_known_hosts(name)
