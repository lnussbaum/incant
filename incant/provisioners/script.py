from .base import Provisioner


class Script(Provisioner):
    config_key = "script"

    def validate_config(self, instance_name: str, config: str):
        pass

    def provision(self, instance_name: str, config: str):
        """Run a shell script."""
        self.incus.run_script(instance_name, config)
