import os
import sys
from pathlib import Path

import click
import yaml
from jinja2 import Environment, FileSystemLoader
from mako.template import Template

from .constants import CLICK_STYLE
from .exceptions import ConfigurationError


class ConfigManager:
    def __init__(self, config_path: str = None, verbose: bool = False, no_config: bool = False):
        self.config_path = config_path
        self.verbose = verbose
        self.no_config = no_config
        self.config_data = None
        if not self.no_config:
            self.config_data = self.load_config()

    def find_config_file(self):
        config_paths = [
            (
                Path(self.config_path) if self.config_path else None
            ),  # First, check if a config is passed directly
            *(
                Path(os.getcwd()) / f"incant{ext}"
                for ext in [
                    ".yaml",
                    ".yaml.j2",
                    ".yaml.mako",
                ]
            ),
            *(
                Path(os.getcwd()) / f".incant{ext}"
                for ext in [
                    ".yaml",
                    ".yaml.j2",
                    ".yaml.mako",
                ]
            ),
        ]
        for path in filter(None, config_paths):
            if path.is_file():
                if self.verbose:
                    click.secho(f"Config found at: {path}", **CLICK_STYLE["success"])
                return path
        # If no config is found, return None
        return None

    def load_config(self):
        try:
            # Find the config file first
            config_file = self.find_config_file()

            if config_file is None:
                return None

            # Read the config file content
            with open(config_file, "r", encoding="utf-8") as file:
                content = file.read()

            # If the config file ends with .yaml.j2, use Jinja2
            if config_file.suffix == ".j2":
                if self.verbose:
                    click.secho("Using Jinja2 template processing...", **CLICK_STYLE["info"])
                env = Environment(loader=FileSystemLoader(os.getcwd()))
                template = env.from_string(content)
                content = template.render()

            # If the config file ends with .yaml.mako, use Mako
            elif config_file.suffix == ".mako":
                if self.verbose:
                    click.secho("Using Mako template processing...", **CLICK_STYLE["info"])
                template = Template(content)
                content = template.render()

            # Load the YAML data from the processed content
            config_data = yaml.safe_load(content)

            if self.verbose:
                click.secho(
                    f"Config loaded successfully from {config_file}",
                    **CLICK_STYLE["success"],
                )
            return config_data
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing YAML file: {e}") from e
        except FileNotFoundError as exc:
            raise ConfigurationError(f"Config file not found: {config_file}") from exc

    def dump_config(self):
        if not self.config_data:
            raise ConfigurationError("No configuration to dump")
        try:
            yaml.dump(self.config_data, sys.stdout, default_flow_style=False, sort_keys=False)
        except Exception as e:  # pylint: disable=broad-exception-caught
            click.secho(f"Error dumping configuration: {e}", **CLICK_STYLE["error"])

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
