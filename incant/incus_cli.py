import subprocess
import json
from typing import List, Dict, Optional
import sys
import tempfile
import os
from pathlib import Path
import click

# click output styles
CLICK_STYLE = {
    "success": {"fg": "green", "bold": True},
    "info": {"fg": "cyan"},
    "warning": {"fg": "yellow"},
    "error": {"fg": "red"},
}


class IncusCLI:
    """
    A Python wrapper for the Incus CLI interface.
    """

    def __init__(self, incus_cmd: str = "incus"):
        self.incus_cmd = incus_cmd

    def _run_command(
        self,
        command: List[str],
        *,
        capture_output: bool = True,
        allow_failure: bool = False,
        exception_on_failure: bool = False,
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
            error_message = f"Failed: {e.stderr.strip()}" if capture_output else "Command failed"
            if allow_failure:
                click.secho(error_message, **CLICK_STYLE["error"])
                return ""
            elif exception_on_failure:
                raise
            else:
                click.secho(error_message, **CLICK_STYLE["error"])
                sys.exit(1)

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

    def create_instance(
        self,
        name: str,
        image: str,
        profiles: Optional[List[str]] = None,
        vm: bool = False,
    ) -> None:
        """Creates a new instance with the optional --vm flag and profiles."""
        command = ["launch", image, name]

        if vm:
            command.append("--vm")  # Add --vm option if vm is True

        if profiles:
            for profile in profiles:
                command.extend(
                    ["--profile", profile]
                )  # Add each profile as a separate --profile <profile>

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
        ]
        self._run_command(command)

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
            exception_on_failure=True,
        )
        return json.loads(output)

    def is_instance_stopped(self, name: str) -> bool:
        return self.get_instance_info(name)["status"] == "Stopped"

    def is_agent_running(self, name: str) -> bool:
        return self.get_instance_info(name).get("state", {}).get("processes", -2) > 0

    def is_agent_usable(self, name: str) -> bool:
        try:
            self.exec(name, ["true"], exception_on_failure=True, quiet=True)
            return True
        except subprocess.CalledProcessError as e:
            if e.stderr.strip() == "Error: VM agent isn't currently running":
                return False
            else:
                raise

    def is_instance_booted(self, name: str) -> bool:
        try:
            self.exec(name, ["which", "systemctl"], quiet=True, exception_on_failure=True)
        except Exception as exc:
            # no systemctl in instance. We assume it booted
            # return True
            raise RuntimeError("systemctl not found in instance") from exc
        try:
            systemctl = self.exec(
                name,
                ["systemctl", "is-system-running"],
                quiet=True,
                exception_on_failure=True,
            ).strip()
        except subprocess.CalledProcessError:
            return False
        return systemctl == "running"

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
