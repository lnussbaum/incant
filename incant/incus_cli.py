import subprocess
import json
from typing import List, Dict, Optional
import sys
from pathlib import Path
import tempfile
import os


import time


from .exceptions import IncusCommandError, InstanceError
from .reporter import Reporter


class IncusCLI:
    """
    A Python wrapper for the Incus CLI interface.
    """

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
            result = subprocess.run(
                full_command, capture_output=capture_output, text=True, check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            error_message = (
                f"Failed: {e.stderr.strip()}"
                if capture_output and e.stderr is not None
                else f"Command {' '.join(full_command)} failed"
            )
            if allow_failure:
                self.reporter.error(error_message)
                return e.stdout
            raise IncusCommandError(
                error_message,
                command=" ".join(full_command),
                stderr=e.stderr,
            ) from e

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
        if self.is_instance(name):
            raise InstanceError(f'Instance "{name}" already exists.')
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
                    return True  # Success!
                except IncusCommandError:
                    if attempt < 2:
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
                self.file_push(name, temp_path, temp_path, quiet=True)

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

    def file_push(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        instance_name: str,
        source: str,
        target: str,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
        mode: Optional[str] = None,
        recursive: bool = False,
        create_dirs: bool = False,
        quiet: bool = False,
    ) -> None:
        """Copies a file or directory to an Incus instance."""
        if not quiet:
            self.reporter.success(f"Copying {source} to {instance_name}:{target}...")
        command = ["file", "push"]
        if uid is not None:
            command.extend(["--uid", str(uid)])
        if gid is not None:
            command.extend(["--gid", str(gid)])
        if mode is not None:
            command.extend(["--mode", mode])
        if recursive:
            command.append("--recursive")
        if create_dirs:
            command.append("--create-dirs")
        command.extend([source, f"{instance_name}{target}"])
        self._run_command(command, capture_output=False, quiet=quiet)

    def shell(self, name: str) -> None:
        """Opens an interactive shell in the specified Incus instance."""
        self.reporter.success(f"Opening shell in {name}...")
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
