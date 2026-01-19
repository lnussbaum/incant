from typing import Union

from .base import Provisioner


class Script(Provisioner):
    config_key = "script"

    def validate_config(self, instance_name: str, config: Union[bool, dict, str]):
        pass

    def provision(self, instance_name: str, config: Union[bool, dict, str]):
        """Run a shell script."""
        if not isinstance(config, str):
            raise TypeError(f"Config for Script provisioner must be a str, got {type(config)}")
        self.incus.run_script(instance_name, config)
