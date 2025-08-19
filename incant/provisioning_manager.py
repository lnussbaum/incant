"""
Provisioning management for Incant.
"""

from .incus_cli import IncusCLI
from .reporter import Reporter


class ProvisionManager:
    """Handles provisioning of instances."""

    def __init__(self, incus_cli: IncusCLI, reporter: Reporter):
        self.incus = incus_cli
        self.reporter = reporter

    def provision(self, instance_name: str, provisions: list | str):
        """Provision an instance."""
        if provisions:
            self.reporter.success(f"Provisioning instance {instance_name}...")

            # Handle provisioning steps
            if isinstance(provisions, str):
                self.incus.provision(instance_name, provisions)
            elif isinstance(provisions, list):
                for step in provisions:
                    if isinstance(step, dict) and "copy" in step:
                        self.incus.copy(instance_name, **step["copy"])
                    elif isinstance(step, dict) and "ssh" in step:
                        self.incus.ssh_setup(instance_name, step["ssh"])
                    else:
                        self.reporter.info("Running provisioning step ...")
                        self.incus.provision(instance_name, step)
        else:
            self.reporter.info(f"No provisioning found for {instance_name}.")
