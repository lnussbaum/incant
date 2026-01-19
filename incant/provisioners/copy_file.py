import re
from typing import Union

from ..exceptions import ConfigurationError
from ..types import FilePushConfig
from .base import Provisioner


class CopyFile(Provisioner):
    config_key = "copy"

    def validate_config(self, instance_name: str, config: Union[bool, dict, str]):
        if not isinstance(config, dict):
            raise ConfigurationError(
                f"Provisioning 'copy' step in instance '{instance_name}' must have a dictionary value."
            )

        required_fields = ["source", "target"]
        missing = [field for field in required_fields if field not in config]
        if missing:
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{instance_name}' is missing required "
                    f"field(s): {', '.join(missing)}."
                )
            )
        if not isinstance(config["source"], str) or not isinstance(config["target"], str):
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{instance_name}' "
                    "must have string 'source' and 'target'."
                )
            )

        if "uid" in config and not isinstance(config["uid"], int):
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{instance_name}' "
                    "has invalid 'uid': must be an integer."
                )
            )
        if "gid" in config and not isinstance(config["gid"], int):
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{instance_name}' "
                    "has invalid 'gid': must be an integer."
                )
            )
        if "mode" in config:
            mode_val = config["mode"]
            if not isinstance(mode_val, str):
                raise ConfigurationError(
                    (
                        f"Provisioning 'copy' step in instance '{instance_name}' has invalid 'mode': "
                        "must be a string like '0644'."
                    )
                )
            if re.fullmatch(r"[0-7]{3,4}", mode_val) is None:
                raise ConfigurationError(
                    (
                        f"Provisioning 'copy' step in instance '{instance_name}' has invalid 'mode': "
                        "must be 3-4 octal digits (e.g., '644' or '0644')."
                    )
                )
        if "recursive" in config and not isinstance(config["recursive"], bool):
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{instance_name}'"
                    "has invalid 'recursive': must be a boolean."
                )
            )
        if "create_dirs" in config and not isinstance(config["create_dirs"], bool):
            raise ConfigurationError(
                (
                    f"Provisioning 'copy' step in instance '{instance_name}' "
                    "has invalid 'create_dirs': must be a boolean."
                )
            )

    def provision(self, instance_name: str, config: Union[bool, dict, str]):
        """Copy a file to the instance."""
        if not isinstance(config, dict):
            raise TypeError(f"Config for CopyFile provisioner must be a dict, got {type(config)}")
        config["instance_name"] = instance_name
        self.incus.file_push(FilePushConfig(**config))
