"""
Provisioning management for Incant.
"""

import glob
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Union

from .exceptions import IncusCommandError
from .incus_cli import IncusCLI
from .reporter import Reporter
from .types import ProvisionSteps


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
                        self.incus.file_push(instance_name, **step["copy"])
                    elif isinstance(step, dict) and "ssh" in step:
                        self.ssh_setup(instance_name, step["ssh"])
                    else:
                        self.reporter.info("Running provisioning step ...")
                        self.incus.run_script(instance_name, step)
        else:
            self.reporter.info(f"No provisioning found for {instance_name}.")

    def clean_known_hosts(self, name: str) -> None:
        """Remove an instance's name from the known_hosts file and add the new host key."""
        self.reporter.success(
            f"Updating {name} in known_hosts to avoid SSH warnings...",
        )
        known_hosts_path = Path.home() / ".ssh" / "known_hosts"
        if known_hosts_path.exists():
            try:
                # Remove existing entry
                subprocess.run(["ssh-keygen", "-R", name], check=False, capture_output=True)
            except FileNotFoundError as e:
                raise IncusCommandError("ssh-keygen not found, cannot clean known_hosts.") from e

        # Initiate a connection to accept the new host key
        try:
            subprocess.run(
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

    def ssh_setup(self, name: str, ssh_config: Union[dict, bool]) -> None:
        """Install SSH server and copy authorized_keys."""
        if isinstance(ssh_config, bool):
            ssh_config = {"clean_known_hosts": True}

        self.reporter.success(f"Installing SSH server in {name}...")
        try:
            self.incus.exec(
                name,
                ["sh", "-c", "apt-get update && apt-get -y install ssh"],
                capture_output=False,
            )
        except IncusCommandError:
            self.reporter.error(
                f"Failed to install SSH server in {name}. "
                "Currently, only apt-based systems are supported for ssh-setup.",
            )
            return

        self.reporter.success(f"Filling authorized_keys in {name}...")
        self.incus.exec(name, ["mkdir", "-p", "/root/.ssh"])

        # Determine the content for authorized_keys
        authorized_keys_content = ""
        source_path_str = (
            ssh_config.get("authorized_keys") if isinstance(ssh_config, dict) else None
        )

        if source_path_str:
            source_path = Path(source_path_str).expanduser()
            if source_path.exists():
                with open(source_path, "r", encoding="utf-8") as f:
                    authorized_keys_content = f.read()
            else:
                self.reporter.warning(
                    f"Provided authorized_keys file not found: {source_path}. Skipping copy.",
                )
        else:
            # Concatenate all public keys from ~/.ssh/id_*.pub
            ssh_dir = Path.home() / ".ssh"
            pub_keys_content = []
            key_files = glob.glob(os.path.join(ssh_dir, "id_*.pub"))

            for key_file_path in key_files:
                with open(key_file_path, "r", encoding="utf-8") as f:
                    pub_keys_content.append(f.read().strip())

            if pub_keys_content:
                authorized_keys_content = "\n".join(pub_keys_content) + "\n"
            else:
                self.reporter.warning(
                    "No public keys found in ~/.ssh/id_*.pub and no authorized_keys file provided. "
                    "SSH access might not be possible without a password.",
                )

        if authorized_keys_content:
            fd, temp_path = tempfile.mkstemp(prefix="incant_authorized_keys_")
            try:
                with os.fdopen(fd, "w") as temp_file:
                    temp_file.write(authorized_keys_content)

                self.incus.file_push(
                    name,
                    temp_path,
                    "/root/.ssh/authorized_keys",
                    uid=0,
                    gid=0,
                    quiet=True,
                )
            finally:
                os.remove(temp_path)

        if ssh_config.get("clean_known_hosts"):
            self.clean_known_hosts(name)
