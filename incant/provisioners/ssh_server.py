import glob
import os
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from typing import TypedDict, Union

from ..exceptions import ConfigurationError, IncusCommandError
from ..types import FilePushConfig
from .base import Provisioner


class PackageManager(TypedDict):
    check_cmd: str
    install_cmds: list[str]


class SSHServer(Provisioner):
    config_key = "ssh"

    def validate_config(self, instance_name: str, config: Union[bool, dict, str]):
        if not isinstance(config, (bool, dict)):
            raise ConfigurationError(
                f"Provisioning 'ssh' step in instance '{instance_name}' "
                "must have a boolean or dictionary value."
            )

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
                    "dnf -y -q install openssh-server",
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
            except IncusCommandError:
                continue  # Try next package manager

            for cmd in pm["install_cmds"]:
                self.incus.exec(name, ["sh", "-c", cmd], capture_output=False)
            return True  # Installed
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

    def provision(self, instance_name: str, config: Union[bool, dict, str]) -> None:
        """Install SSH server and copy authorized_keys."""
        if not isinstance(config, (bool, dict)):
            raise TypeError(f"Config for SSHServer provisioner must be a bool or dict, got {type(config)}")
        if isinstance(config, bool):
            config = {"clean_known_hosts": True}

        self.reporter.success(f"Installing SSH server in {instance_name}...")
        if not self._install_ssh_server(instance_name):
            self.reporter.error(
                f"Failed to install SSH server in {instance_name}. "
                "No supported package manager (apt-get, dnf, pacman) found.",
            )
            return

        content = self._get_authorized_keys_content(config)
        self._write_authorized_keys(instance_name, content)

        if config.get("clean_known_hosts"):
            self.clean_known_hosts(instance_name)
