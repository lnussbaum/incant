import os
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from jinja2 import exceptions as jinja_exceptions
from mako import exceptions as mako_exceptions
from mako.template import Template

from .exceptions import ConfigurationError
from .reporter import Reporter
from .types import InstanceConfig, InstanceDict


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
        self._config_data = None
        self.instance_configs: InstanceDict = {}
        if not self.no_config:
            try:
                self._config_data = self.load_config()
                if self._config_data:
                    self.instance_configs = self.get_instance_configs()
                    self.validate_config()
            except (ConfigurationError, TypeError) as e:
                # Re-raise to be caught by the CLI or tests
                raise ConfigurationError(e) from e

    def get_instance_configs(self) -> InstanceDict:
        """Parses the raw config data and returns a dictionary of InstanceConfig objects."""
        instance_configs = {}
        instances_data = self._config_data.get("instances", {})
        for instance_name, instance_data in instances_data.items():
            if instance_data is None:
                instance_data = {}

            if "image" not in instance_data:
                raise ConfigurationError(
                    f"Instance '{instance_name}' is missing required 'image' field."
                )

            instance_data_copy = instance_data.copy()
            instance_data_copy["name"] = instance_name
            if "type" in instance_data_copy:
                instance_data_copy["instance_type"] = instance_data_copy.pop("type")
            if "pre-launch" in instance_data_copy:
                instance_data_copy["pre_launch_cmds"] = instance_data_copy.pop(
                    "pre-launch"
                )
            instance_configs[instance_name] = InstanceConfig(**instance_data_copy)
        return instance_configs

    def find_config_file(self):
        if self.config_path:
            explicit_path = Path(self.config_path)
            if explicit_path.is_file():
                if self.verbose:
                    self.reporter.success(f"Config found at: {explicit_path}")
                return explicit_path
            else:
                return None

        base_names = ["incant", ".incant"]
        extensions = [".yaml", ".yaml.j2", ".yaml.mako"]
        cwd = Path.cwd()

        for name in base_names:
            for ext in extensions:
                path = cwd / f"{name}{ext}"
                if path.is_file():
                    if self.verbose:
                        self.reporter.success(f"Config found at: {path}")
                    return path
        return None

    def load_config(self):
        config_file = self.find_config_file()
        if config_file is None:
            raise ConfigurationError("Config file not found")

        try:
            # Read the config file content
            with open(config_file, "r", encoding="utf-8") as file:
                content = file.read()

            # If the config file ends with .yaml.j2, use Jinja2
            if config_file.suffix == ".j2":
                if self.verbose:
                    self.reporter.info("Using Jinja2 template processing...")
                env = Environment(loader=FileSystemLoader(os.getcwd()), autoescape=True)
                template = env.from_string(content)
                content = template.render()

            # If the config file ends with .yaml.mako, use Mako
            elif config_file.suffix == ".mako":
                if self.verbose:
                    self.reporter.info("Using Mako template processing...")
                template = Template(content)  # nosec B702
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
        if not self._config_data:
            raise ConfigurationError("No configuration to dump")
        try:
            yaml.dump(self._config_data, sys.stdout, default_flow_style=False, sort_keys=False)
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
                f"Provisioning 'ssh' step in instance '{name}' must have a boolean "
                "or dictionary value."
            )

    def _validate_provisioning(self, instance: InstanceConfig, name: str):
        if instance.provision is not None:
            provisions = instance.provision
            if isinstance(provisions, list):
                for step_idx, step in enumerate(provisions):
                    self._validate_provision_step(step, step_idx, name)
            elif not isinstance(provisions, str):
                raise ConfigurationError(
                    f"Provisioning for instance '{name}' must be a string or a list of steps."
                )

    def _validate_pre_launch(self, instance: InstanceConfig, name: str):
        if instance.pre_launch_cmds is not None:
            pre_launch_cmds = instance.pre_launch_cmds
            if not isinstance(pre_launch_cmds, list):
                raise ConfigurationError(
                    f"Pre-launch commands for instance '{name}' must be a list of strings."
                )
            for cmd_idx, cmd in enumerate(pre_launch_cmds):
                if not isinstance(cmd, str):
                    raise ConfigurationError(
                        f"Pre-launch command {cmd_idx} in instance '{name}' must be a string."
                    )

    def validate_config(self):
        if not self.instance_configs:
            raise ConfigurationError("No instances found in config")

        for name, instance_config in self.instance_configs.items():
            

            # Validate 'provision' field
            self._validate_provisioning(instance_config, name)
            self._validate_pre_launch(instance_config, name)
