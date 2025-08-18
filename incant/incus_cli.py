import subprocess
import json
from typing import List, Dict, Optional, Union
import sys
import tempfile
import os
import time
from pathlib import Path
import glob
import click

# click output styles
from .constants import CLICK_STYLE
from .exceptions import IncusCommandError, InstanceError


class IncusCLI:
    """
    A Python wrapper for the Incus CLI interface.
    """

    def __init__(self, incus_cmd: str = "incus"):
        self.incus_cmd = incus_cmd

    def _run_command(  # pylint: disable=too-many-arguments
        self,
        command: List[str],
        *,
        capture_output: bool = True,
        allow_failure: bool = False,
        quiet: bool = False,
    ) -> str:
        """Executes an Incus CLI command and returns the output. Optionally allows failure."""
        try:
            full_command = [self.incus_cmd] + command
            if not quiet:
                click.secho(f"-> {' '.join(full_command)}", **CLICK_STYLE["info"])
            result = subprocess.run(
                full_command, capture_output=capture_output, text=True, check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            error_message = (
                f"Failed: {e.stderr.strip()}"
                if capture_output
                else f"Command {' '.join(full_command)} failed"
            )
            if allow_failure:
                click.secho(error_message, **CLICK_STYLE["error"])
                return e.stdout
            raise IncusCommandError(error_message, command=" ".join(full_command)) from e

    def exec(self, name: str, command: List[str], cwd: str = None, **kwargs) -> str:
        cmd = ["exec"]
        if cwd:
            cmd.extend(["--cwd", cwd])
        cmd.extend([name, "--"] + command)
        return self._run_command(cmd, **kwargs)

    def create_project(self, name: str) -> None:
        """Creates a new project."""
        command = ["project", "create", name]
        self._run_command(command)

    def create_instance(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        name: str,
        image: str,
        profiles: Optional[List[str]] = None,
        vm: bool = False,
        config: Optional[Dict[str, str]] = None,
        devices: Optional[Dict[str, Dict[str, str]]] = None,
        network: Optional[str] = None,
        instance_type: Optional[str] = None,
    ) -> None:
        """Creates a new instance with optional parameters."""
        command = ["launch", image, name]

        if vm:
            command.append("--vm")

        if profiles:
            for profile in profiles:
                command.extend(["--profile", profile])

        if config:
            for key, value in config.items():
                command.extend(["--config", f"{key}={value}"])

        if devices:
            for dev_name, dev_attrs in devices.items():
                dev_str = f"{dev_name}"
                for k, v in dev_attrs.items():
                    dev_str += f",{k}={v}"
                command.extend(["--device", dev_str])

        if network:
            command.extend(["--network", network])

        if instance_type:
            command.extend(["--type", instance_type])

        self._run_command(command)

    def create_shared_folder(self, name: str) -> None:
        curdir = Path.cwd()
        command = [
            "config",
            "device",
            "add",
            name,
            f"{name}_shared_incant",
            "disk",
            f"source={curdir}",
            "path=/incant",
            "shift=true",  # First attempt with shift enabled
        ]

        try:
            self._run_command(command, capture_output=False)
        except IncusCommandError:
            click.secho(
                "Shared folder creation failed. Retrying without shift=true...",
                **CLICK_STYLE["warning"],
            )
            command.remove("shift=true")  # Remove shift option and retry
            self._run_command(command, capture_output=False)

        # Sometimes the creation of shared directories fails
        # (see https://github.com/lxc/incus/issues/1881)
        # So we retry up to 10 times
        for _ in range(10):
            # First, check a few times if the mount is just slow
            for attempt in range(3):
                try:
                    self.exec(
                        name,
                        ["grep", "-wq", "/incant", "/proc/mounts"],
                        capture_output=False,
                    )
                    return True  # Success!
                except IncusCommandError:
                    if attempt < 2:
                        time.sleep(1)
                    # On last attempt, fall through to re-create device

            click.secho(
                "Shared folder creation failed (/incant not mounted). Retrying...",
                **CLICK_STYLE["warning"],
            )
            self._run_command(
                ["config", "device", "remove", name, f"{name}_shared_incant"],
                capture_output=False,
            )
            self._run_command(command, capture_output=False)

        raise InstanceError("Shared folder creation failed.")

    def destroy_instance(self, name: str) -> None:
        """Destroy (stop if needed, then delete) an instance."""
        self._run_command(["delete", "--force", name], allow_failure=True)

    def get_current_project(self) -> str:
        return self._run_command(["project", "get-current"], quiet=True).strip()

    def get_instance_info(self, name: str) -> Dict:
        """Gets detailed information about an instance."""
        output = self._run_command(
            [
                "query",
                f"/1.0/instances/{name}?project={self.get_current_project()}&recursion=1",
            ],
            quiet=True,
        )
        return json.loads(output)

    def is_instance_stopped(self, name: str) -> bool:
        return self.get_instance_info(name)["status"] == "Stopped"

    def is_agent_running(self, name: str) -> bool:
        return self.get_instance_info(name).get("state", {}).get("processes", -2) > 0

    def is_agent_usable(self, name: str) -> bool:
        try:
            self.exec(name, ["true"], quiet=True)
            return True
        except IncusCommandError as e:
            if e.stderr.strip() == "Error: VM agent isn't currently running":
                return False
            raise

    def is_instance_booted(self, name: str) -> bool:
        try:
            self.exec(name, ["which", "systemctl"], quiet=True)
        except Exception as exc:
            # no systemctl in instance. We assume it booted
            # return True
            raise RuntimeError("systemctl not found in instance") from exc
        systemctl = self.exec(
            name,
            ["systemctl", "is-system-running"],
            quiet=True,
            allow_failure=True,
        ).strip()

        return systemctl in ["running", "degraded"]

    def is_instance_ready(self, name: str, verbose: bool = False) -> bool:
        if not self.is_agent_running(name):
            return False
        if verbose:
            click.secho("Agent is running, testing if usable...", **CLICK_STYLE["info"])
        if not self.is_agent_usable(name):
            return False
        if verbose:
            click.secho("Agent is usable, checking if system booted...", **CLICK_STYLE["info"])
        if not self.is_instance_booted(name):
            return False
        return True

    def is_instance(self, name: str) -> bool:
        """Checks if an instance exists."""
        try:
            self.get_instance_info(name)
            return True
        except subprocess.CalledProcessError:
            return False

    def clean_known_hosts(self, name: str) -> None:
        """Remove an instance's name from the known_hosts file and add the new host key."""
        click.secho(
            f"Updating {name} in known_hosts to avoid SSH warnings...", **CLICK_STYLE["success"]
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
            click.secho(
                "ssh command not found, cannot add new host key to known_hosts.",
                **CLICK_STYLE["warning"],
            )

    def provision(self, name: str, provision: str, quiet: bool = True) -> None:
        """Provision an instance with a single command or a multi-line script."""

        if "\n" not in provision:  # Single-line command
            # Change to /incant and then execute the provision command inside
            # sh -c for quoting safety
            self.exec(
                name,
                ["sh", "-c", provision],
                quiet=quiet,
                capture_output=False,
                cwd="/incant",
            )
        else:  # Multi-line script
            # Create a secure temporary file locally
            fd, temp_path = tempfile.mkstemp(prefix="incant_")

            try:
                # Write the script content to the temporary file
                with os.fdopen(fd, "w") as temp_file:
                    temp_file.write(provision)

                # Copy the file to the instance
                self._run_command(["file", "push", temp_path, f"{name}{temp_path}"], quiet=quiet)

                # Execute the script after copying
                self.exec(
                    name,
                    [
                        "sh",
                        "-c",
                        f"chmod +x {temp_path} && {temp_path} && rm {temp_path}",
                    ],
                    quiet=quiet,
                    capture_output=False,
                )
            finally:
                # Clean up the local temporary file
                os.remove(temp_path)

    def copy(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        instance_name: str,
        source: str,
        target: str,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
        mode: Optional[str] = None,
        recursive: bool = False,
        create_empty_directories: bool = False,
        compression: str = "none",
    ) -> None:
        """Copies a file or directory to an Incus instance."""
        click.secho(f"Copying {source} to {instance_name}:{target}...", **CLICK_STYLE["success"])
        command = ["file", "push"]
        if uid is not None:
            command.extend(["--uid", str(uid)])
        if gid is not None:
            command.extend(["--gid", str(gid)])
        if mode is not None:
            command.extend(["--mode", mode])
        if recursive:
            command.append("--recursive")
        if create_empty_directories:
            command.append("--create-empty-directories")
        if compression != "none":
            command.extend(["--compression", compression])
        command.extend([source, f"{instance_name}{target}"])
        self._run_command(command, capture_output=False)

    def ssh_setup(self, name: str, ssh_config: Union[dict, bool]) -> None:
        """Install SSH server and copy authorized_keys."""
        if isinstance(ssh_config, bool):
            ssh_config = {"clean_known_hosts": True}

        click.secho(f"Installing SSH server in {name}...", **CLICK_STYLE["success"])
        try:
            self.exec(
                name,
                ["sh", "-c", "apt-get update && apt-get -y install ssh"],
                capture_output=False,
            )
        except IncusCommandError:
            click.secho(
                f"Failed to install SSH server in {name}. "
                "Currently, only apt-based systems are supported for ssh-setup.",
                **CLICK_STYLE["error"],
            )
            return

        click.secho(f"Filling authorized_keys in {name}...", **CLICK_STYLE["success"])
        self.exec(name, ["mkdir", "-p", "/root/.ssh"])

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
                click.secho(
                    f"Provided authorized_keys file not found: {source_path}. Skipping copy.",
                    **CLICK_STYLE["warning"],
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
                click.secho(
                    "No public keys found in ~/.ssh/id_*.pub and no authorized_keys file provided. "
                    "SSH access might not be possible without a password.",
                    **CLICK_STYLE["warning"],
                )

        if authorized_keys_content:
            fd, temp_path = tempfile.mkstemp(prefix="incant_authorized_keys_")
            try:
                with os.fdopen(fd, "w") as temp_file:
                    temp_file.write(authorized_keys_content)

                self._run_command(
                    [
                        "file",
                        "push",
                        temp_path,
                        f"{name}/root/.ssh/authorized_keys",
                        "--uid",
                        "0",
                        "--gid",
                        "0",
                    ],
                    capture_output=False,
                )
            finally:
                os.remove(temp_path)

        if ssh_config.get("clean_known_hosts"):
            self.clean_known_hosts(name)

    def shell(self, name: str) -> None:
        """Opens an interactive shell in the specified Incus instance."""
        click.secho(f"Opening shell in {name}...", **CLICK_STYLE["success"])
        try:
            subprocess.run(
                [self.incus_cmd, "shell", name],
                check=True,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
        except subprocess.CalledProcessError as e:
            raise InstanceError(f"Failed to open shell in {name}: {e}") from e
