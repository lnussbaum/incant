import os
import sys
import re
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, exceptions as jinja_exceptions
from mako.template import Template
from mako import exceptions as mako_exceptions


from .exceptions import ConfigurationError
from .reporter import Reporter


class ConfigManager:
    def __init__(
        self,
        reporter: Reporter,
        config_path: str = None,
        verbose: bool = False,
        no_config: bool = False,
    ):
        self.reporter = reporter
        self.config_path = config_path
        self.verbose = verbose
        self.no_config = no_config
        self.config_data = None
        if not self.no_config:
            try:
                self.config_data = self.load_config()
            except ConfigurationError as e:
                # Re-raise to be caught by the CLI or tests
                raise e

    def find_config_file(self):
        search_paths = []
        if self.config_path:
            search_paths.append(Path(self.config_path))

        base_names = ["incant", ".incant"]
        extensions = [".yaml", ".yaml.j2", ".yaml.mako"]
        cwd = Path.cwd()

        for name in base_names:
            for ext in extensions:
                search_paths.append(cwd / f"{name}{ext}")

        for path in search_paths:
            if path.is_file():
                if self.verbose:
                    self.reporter.success(f"Config found at: {path}")
                return path
        # If no config is found, return None
        return None

    def load_config(self):
        config_file = self.find_config_file()
        if config_file is None:
            return None

        try:
            # Read the config file content
            with open(config_file, "r", encoding="utf-8") as file:
                content = file.read()

            # If the config file ends with .yaml.j2, use Jinja2
            if config_file.suffix == ".j2":
                if self.verbose:
                    self.reporter.info("Using Jinja2 template processing...")
                env = Environment(loader=FileSystemLoader(os.getcwd()))
                template = env.from_string(content)
                content = template.render()

            # If the config file ends with .yaml.mako, use Mako
            elif config_file.suffix == ".mako":
                if self.verbose:
                    self.reporter.info("Using Mako template processing...")
                template = Template(content)
                content = template.render()

            # Load the YAML data from the processed content
            config_data = yaml.safe_load(content)

            if self.verbose:
                self.reporter.success(f"Config loaded successfully from {config_file}")
            return config_data

        except FileNotFoundError as exc:
            raise ConfigurationError(f"Config file not found: {config_file}") from exc
        except (jinja_exceptions.TemplateError, mako_exceptions.MakoException) as e:
            raise ConfigurationError(f"Error rendering template {config_file}: {e}") from e
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing YAML file {config_file}: {e}") from e

    def dump_config(self):
        if not self.config_data:
            raise ConfigurationError("No configuration to dump")
        try:
            yaml.dump(self.config_data, sys.stdout, default_flow_style=False, sort_keys=False)
        except Exception as e:  # pylint: disable=broad-exception-caught
            raise ConfigurationError(f"Error dumping configuration: {e}") from e

    def _validate_provision_step(self, step, step_idx, name):
        if isinstance(step, str):
            return

        if not isinstance(step, dict):
            raise ConfigurationError(
                f"Provisioning step {step_idx} in instance '{name}' "
                "must be a string or a dictionary."
            )

        if len(step) != 1:
            raise ConfigurationError(
                f"Provisioning step {step_idx} in instance '{name}' "
                "must have exactly one key (e.g., 'copy' or 'ssh')."
            )

        key, value = list(step.items())[0]

        if key not in ["copy", "ssh"]:
            raise ConfigurationError(
                f"Unknown provisioning step type '{key}' in instance '{name}'. "
                "Accepted types are 'copy' or 'ssh'."
            )

        if key == "copy":
            if not isinstance(value, dict):
                raise ConfigurationError(
                    f"Provisioning 'copy' step in instance '{name}' must have a dictionary value."
                )
            self._validate_copy_step(value, name)

        if key == "ssh":
            self._validate_ssh_step(value, name)

    def _validate_copy_step(self, value, name):
        required_fields = ["source", "target"]
        missing = [field for field in required_fields if field not in value]
        if missing:
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{name}' is missing required "
                    f"field(s): {', '.join(missing)}."
                )
            )
        if not isinstance(value["source"], str) or not isinstance(value["target"], str):
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{name}' must have string "
                    "'source' and 'target'."
                )
            )

        if "uid" in value and not isinstance(value["uid"], int):
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{name}' has invalid 'uid': "
                    "must be an integer."
                )
            )
        if "gid" in value and not isinstance(value["gid"], int):
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{name}' has invalid 'gid': "
                    "must be an integer."
                )
            )
        if "mode" in value:
            mode_val = value["mode"]
            if not isinstance(mode_val, str):
                raise ConfigurationError(
                    (
                        f"Provisioning 'copy' step in instance '{name}' has invalid 'mode': "
                        "must be a string like '0644'."
                    )
                )
            if re.fullmatch(r"[0-7]{3,4}", mode_val) is None:
                raise ConfigurationError(
                    (
                        f"Provisioning 'copy' step in instance '{name}' has invalid 'mode': "
                        "must be 3-4 octal digits (e.g., '644' or '0644')."
                    )
                )
        if "recursive" in value and not isinstance(value["recursive"], bool):
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{name}' has invalid 'recursive': "
                    "must be a boolean."
                )
            )
        if "create_dirs" in value and not isinstance(value["create_dirs"], bool):
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{name}' has invalid "
                    "'create_dirs': must be a boolean."
                )
            )

    def _validate_ssh_step(self, value, name):
        if not isinstance(value, (bool, dict)):
            raise ConfigurationError(
                f"Provisioning 'ssh' step in instance '{name}' must have a boolean or dictionary value."
            )

    def _validate_provisioning(self, instance, name):
        if "provision" in instance and instance["provision"] is not None:
            provisions = instance["provision"]
            if isinstance(provisions, list):
                for step_idx, step in enumerate(provisions):
                    self._validate_provision_step(step, step_idx, name)
            elif not isinstance(provisions, str):
                raise ConfigurationError(
                    f"Provisioning for instance '{name}' must be a string or a list of steps."
                )

    def validate_config(self):
        if not self.config_data:
            raise ConfigurationError("No configuration loaded.")
        if "instances" not in self.config_data:
            raise ConfigurationError("No instances found in config")

        accepted_fields = {
            "image",
            "vm",
            "profiles",
            "config",
            "devices",
            "network",
            "type",
            "wait",
            "provision",
            "shared_folder",
        }

        # The top-level keys of the instances dictionary are the names
        for name, instance in self.config_data["instances"].items():
            if "image" not in instance:
                raise ConfigurationError(f"Instance '{name}' is missing required 'image' field.")

            for field in instance:
                if field not in accepted_fields:
                    raise ConfigurationError(f"Unknown field '{field}' in instance '{name}'.")

            # Validate 'provision' field
            self._validate_provisioning(instance, name)
