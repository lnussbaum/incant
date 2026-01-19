import json
import os
import shlex
import subprocess  # nosec B404
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

from .exceptions import IncusCommandError, InstanceError
from .reporter import Reporter
from .types import FilePushConfig, InstanceConfig


class IncusCLI:
    """
    A Python wrapper for the Incus CLI interface.
    """

    MAX_RETRY_ATTEMPTS = 2

    def __init__(self, reporter: Reporter, incus_cmd: str = "incus"):
        self.reporter = reporter
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
                self.reporter.info(f"-> {' '.join(full_command)}")
            result = subprocess.run(  # nosec B603
                full_command, capture_output=capture_output, text=True, check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            error_message = f"Command {' '.join(full_command)} failed"
            if capture_output and e.stderr and e.stderr.strip():
                error_message = f"Failed: {e.stderr.strip()}"

            if allow_failure:
                self.reporter.error(error_message)
                return e.stdout
            raise IncusCommandError(
                error_message,
                command=" ".join(full_command),
                stderr=e.stderr,
            ) from e

    def exec(self, name: str, command: List[str], cwd: Optional[str] = None, **kwargs) -> str:
        cmd = ["exec"]
        if cwd:
            cmd.extend(["--cwd", cwd])
        cmd.extend([name, "--"] + command)
        return self._run_command(cmd, **kwargs)

    def create_project(self, name: str) -> None:
        """Creates a new project."""
        command = ["project", "create", name]
        self._run_command(command)

    def _build_launch_command(self, instance_config: InstanceConfig) -> List[str]:
        command = [
            "launch" if not instance_config.pre_launch_cmds else "create",
            instance_config.image,
            instance_config.name,
        ]
        if instance_config.vm:
            command.append("--vm")
        if instance_config.profiles:
            for profile in instance_config.profiles:
                command.extend(["--profile", profile])
        if instance_config.config:
            for key, value in instance_config.config.items():
                command.extend(["--config", f"{key}={value}"])
        if instance_config.devices:
            for dev_name, dev_attrs in instance_config.devices.items():
                dev_str = f"{dev_name}"
                for k, v in dev_attrs.items():
                    dev_str += f",{k}={v}"
                command.extend(["--device", dev_str])
        if instance_config.network:
            command.extend(["--network", instance_config.network])
        if instance_config.instance_type:
            command.extend(["--type", instance_config.instance_type])
        return command

    def create_instance(self, instance_config: InstanceConfig) -> None:
        """Creates a new instance with optional parameters."""
        if self.is_instance(instance_config.name):
            raise InstanceError(f'Instance "{instance_config.name}" already exists.')

        command = self._build_launch_command(instance_config)
        self._run_command(command)

        if instance_config.pre_launch_cmds:
            self.reporter.info(f"Executing pre-launch commands for {instance_config.name}...")
            for cmd in instance_config.pre_launch_cmds:
                self._run_command(shlex.split(cmd))
            self.reporter.info(f"Starting {instance_config.name}...")
            self._run_command(["start", instance_config.name])

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
            self.reporter.warning(
                "Shared folder creation failed. Retrying without shift=true...",
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
                    return  # Success!
                except IncusCommandError:
                    if attempt < self.MAX_RETRY_ATTEMPTS:
                        time.sleep(1)
                    # On last attempt, fall through to re-create device

            self.reporter.warning(
                "Shared folder creation failed (/incant not mounted). Retrying...",
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
            if e.stderr and e.stderr.strip() == "Error: VM agent isn't currently running":
                return False
            raise

    def is_instance_booted(self, name: str) -> bool:
        try:
            self.exec(name, ["sh", "-c", "command -v systemctl"], quiet=True)
        except Exception as exc:
            # If systemctl is not found, we cannot determine the boot status.
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
            self.reporter.info("Agent is running, testing if usable...")
        if not self.is_agent_usable(name):
            return False
        if verbose:
            self.reporter.info("Agent is usable, checking if system booted...")
        if not self.is_instance_booted(name):
            return False
        return True

    def is_instance(self, name: str) -> bool:
        """Checks if an instance exists."""
        try:
            self.get_instance_info(name)
            return True
        except IncusCommandError:
            return False

    def run_script(self, name: str, script: str, quiet: bool = True) -> None:
        """Run a script in an instance."""

        if "\n" not in script:  # Single-line command
            # Change to /incant and then execute the provision command inside
            # sh -c for quoting safety
            self.exec(
                name,
                ["sh", "-c", script],
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
                    temp_file.write(script)

                # Copy the file to the instance
                self.file_push(
                    FilePushConfig(
                        instance_name=name,
                        source=temp_path,
                        target=temp_path,
                        quiet=True,
                    )
                )

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

    def file_push(self, file_push_config: FilePushConfig) -> None:
        """Copies a file or directory to an Incus instance."""
        if not file_push_config.quiet:
            self.reporter.success(
                f"Copying {file_push_config.source} to "
                f"{file_push_config.instance_name}:{file_push_config.target}..."
            )
        command = ["file", "push"]
        if file_push_config.uid is not None:
            command.extend(["--uid", str(file_push_config.uid)])
        if file_push_config.gid is not None:
            command.extend(["--gid", str(file_push_config.gid)])
        if file_push_config.mode is not None:
            command.extend(["--mode", file_push_config.mode])
        if file_push_config.recursive:
            command.append("--recursive")
        if file_push_config.create_dirs:
            command.append("--create-dirs")
        command.extend(
            [file_push_config.source, f"{file_push_config.instance_name}{file_push_config.target}"]
        )
        self._run_command(command, capture_output=False, quiet=file_push_config.quiet)

    def shell(self, name: str) -> int:
        """Opens an interactive shell in the specified Incus instance."""
        self.reporter.success(f"Opening shell in {name}...")
        result = subprocess.run(  # nosec B603
            [self.incus_cmd, "shell", name],
            check=False,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return result.returncode
