"""
Provisioning management for Incant.
"""

from .incus_cli import IncusCLI
from .provisioners import REGISTERED_PROVISIONERS
from .reporter import Reporter
from .types import ProvisionSteps


class ProvisionManager:
    """Handles provisioning of instances."""

    def __init__(self, incus_cli: IncusCLI, reporter: Reporter):
        self.incus = incus_cli
        self.reporter = reporter

    def provision(self, instance_name: str, provisions: ProvisionSteps):
        """Provision an instance."""
        if provisions:
            self.reporter.success(f"Provisioning instance {instance_name}...")

            # Handle special "script" single-step provisioning.
            if isinstance(provisions, str):
                provisions = [provisions]

            # Handle provisioning steps
            for step_idx, step in enumerate(provisions):
                self.reporter.info(f"Running provisioning step {step_idx} ...")
                if isinstance(step, dict):
                    step_provisioner_type, step_config = tuple(step.items())[0]
                    REGISTERED_PROVISIONERS[step_provisioner_type](self.incus, self.reporter).provision(
                        instance_name, step_config
                    )
                else:
                    REGISTERED_PROVISIONERS["script"](self.incus, self.reporter).provision(
                        instance_name, step
                    )
        else:
            self.reporter.info(f"No provisioning found for {instance_name}.")
