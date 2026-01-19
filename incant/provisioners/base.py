import abc
import typing
from typing import ClassVar, Union

if typing.TYPE_CHECKING:
    from incant import IncusCLI
from incant.reporter import Reporter

REGISTERED_PROVISIONERS: dict[str, type["Provisioner"]] = {}


class Provisioner(abc.ABC):
    """Abstract class, defining the interface for provisioners."""

    # The name of the key used to identify this provisioner in the
    # incant config.
    config_key: ClassVar[str] = ""

    def __init__(self, incus_cli: "IncusCLI", reporter: Reporter):
        self.incus = incus_cli
        self.reporter = reporter

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        REGISTERED_PROVISIONERS[cls.config_key] = cls

    @abc.abstractmethod
    def validate_config(self, instance_name: str, config: Union[bool, dict, str]):
        """Validate the given config."""
        pass

    @abc.abstractmethod
    def provision(self, instance_name: str, config: Union[bool, dict, str]):
        """Run the provisioning logic."""
        pass
