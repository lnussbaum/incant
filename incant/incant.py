import os
import time
import textwrap
from incant.incus_cli import IncusCLI
from .provisioning_manager import ProvisionManager
from .config_manager import ConfigManager
from .exceptions import IncantError, InstanceError, ConfigurationError
from .reporter import Reporter
from .types import InstanceDict, ProvisionSteps  # pylint: disable=unused-import # noqa: F401


class Incant:
    def __init__(self, reporter: Reporter, **kwargs):
        self.reporter = reporter
        self.verbose = kwargs.get("verbose", False)
        self.no_config = kwargs.get("no_config", False)
        self.config_manager = ConfigManager(
            reporter=self.reporter,
            config_path=kwargs.get("config", None),
            verbose=self.verbose,
            no_config=self.no_config,
        )
        if not self.no_config:
            self.config_manager.validate_config()
        self.incus = IncusCLI(self.reporter)
        self.provisioner = ProvisionManager(self.incus, self.reporter)

    def _get_instances(self, name: str = None) -> InstanceDict:
        """Helper to get instances from config, either all or a specific one."""
        instances = self.config_manager.config_data["instances"]
        if name:
            if name not in instances:
                raise InstanceError(f"Instance '{name}' not found in config.")
            return {name: instances[name]}
        return instances

    def dump_config(self):
        self.config_manager.dump_config()

    def up(self, name=None):
        instances_to_process = self._get_instances(name)

        # Step 1 -- Create instances (we do this for all instances so that they can boot in parallel)
        for instance_name, instance_data in instances_to_process.items():
            # Process the instance
            image = instance_data["image"]

            vm = instance_data.get("vm", False)
            profiles = instance_data.get("profiles", None)
            config = instance_data.get("config", None)
            devices = instance_data.get("devices", None)
            network = instance_data.get("network", None)
            instance_type = instance_data.get("type", None)

            self.reporter.success(
                f"Creating instance {instance_name} with image {image}...",
            )
            self.incus.create_instance(
                instance_name,
                image,
                profiles=profiles,
                vm=vm,
                config=config,
                devices=devices,
                network=network,
                instance_type=instance_type,
            )

        # Step 2 -- Create shared folder and provision
        for instance_name, instance_data in instances_to_process.items():
            # Wait for the agent to become ready before sharing the current directory
            while True:
                if self.incus.is_agent_running(instance_name) and self.incus.is_agent_usable(
                    instance_name
                ):
                    break
                time.sleep(0.3)
            self.reporter.success(
                f"Sharing current directory to {instance_name}:/incant ...",
            )

            # Wait for the instance to become ready if specified in config, or
            # if we want to perform provisioning, or if the instance is a VM (for some
            # reason the VM needs to be running before creating the shared folder)
            if (
                instance_data.get("wait", False)
                or instance_data.get("provision", False)
                or instance_data.get("vm", False)
            ):
                self.reporter.info(
                    f"Waiting for {instance_name} to become ready...",
                )
                while True:
                    if self.incus.is_instance_ready(instance_name, True):
                        self.reporter.success(
                            f"Instance {instance_name} is ready.",
                        )
                        break
                    time.sleep(1)

            if instance_data.get("shared_folder", True):
                self.incus.create_shared_folder(instance_name)

            if instance_data.get("provision", False):
                # Automatically run provisioning after instance creation
                self.provision(instance_name)

    def provision(self, name: str = None):
        instances_to_provision = self._get_instances(name)

        for instance_name, instance_data in instances_to_provision.items():
            provisions = instance_data.get("provision", [])
            self.provisioner.provision(instance_name, provisions)

    def destroy(self, name=None):
        instances_to_destroy = self._get_instances(name)

        for instance_name, _instance_data in instances_to_destroy.items():
            # Check if the instance exists before deleting
            if not self.incus.is_instance(instance_name):
                self.reporter.info(f"Instance '{instance_name}' does not exist.")
                continue

            self.reporter.success(f"Destroying instance {instance_name} ...")
            self.incus.destroy_instance(instance_name)

    def list_instances(self, no_error: bool = False):
        """List all instances defined in the configuration.

        When no_error is True and no configuration is found, do nothing and return successfully.
        """
        if self.config_manager.config_data is None:
            config = self.config_manager.load_config()
            if config is None:
                if no_error:
                    return
                raise ConfigurationError("No configuration loaded.")
            self.config_manager.config_data = config
        # Validate before listing
        self.config_manager.validate_config()
        for instance_name in self.config_manager.config_data["instances"]:
            self.reporter.echo(f"{instance_name}")

    def incant_init(self):
        example_config = textwrap.dedent(
            """
          instances:
            basic-container:
              image: images:ubuntu/24.04
              devices:
                root:
                  size: 1GiB
              wait: true # wait for instance to be ready (incus agent running)
              shared_folder: false # disable shared folder (/incant) setup (default: enabled)
              config: # any incus config options
                limits.processes: 100
            basic-vm:
              image: images:ubuntu/24.04
              vm: true
              type: c1-m1 # 1 CPU, 1GB RAM
            provisioned:
              image: images:debian/13
              provision: # a list of provisioning steps
                - | # first, an inlined script
                  #!/bin/bash
                  set -xe
                  apt-get update
                  apt-get -y install curl ruby
                # then, a script. the path can be relative to the current dir,
                # as incant will 'cd' to /incant, so the script will be available inside the instance
                - examples/provision/web_server.rb
                - ssh: true # configure an ssh server and provide access
                # - ssh: # same with more configuration
                #    clean_known_hosts: true (that's the default)
                #    # authorized_keys: path to file (default: concatenate id_*.pub)
                - copy: # copy a file using 'incus file push'
                    source: ./README.md
                    target: /tmp/README.md
                    mode: "0644"
                    uid: 0
                    gid: 0
            """
        )

        config_path = "incant.yaml"

        if os.path.exists(config_path):
            raise IncantError(f"{config_path} already exists. Aborting.")

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(example_config)

        print(f"Example configuration written to {config_path}")

    def shell(self, name: str = None):
        instance_name = name
        if not instance_name:
            instance_names = list(self.config_manager.config_data["instances"].keys())
            if len(instance_names) == 1:
                instance_name = instance_names[0]
            else:
                raise InstanceError("Multiple instances found. Please specify an instance name")

        if instance_name not in self.config_manager.config_data["instances"]:
            raise InstanceError(f"Instance '{instance_name}' not found in config")

        self.incus.shell(instance_name)
