from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

ProvisionSteps = Union[str, list]
InstanceDict = Dict[str, "InstanceConfig"]


@dataclass
class InstanceConfig:
    """Dataclass for instance configuration."""

    name: str
    image: str
    profiles: Optional[List[str]] = None
    vm: bool = False
    config: Optional[Dict[str, str]] = None
    devices: Optional[Dict[str, Dict[str, str]]] = None
    network: Optional[str] = None
    instance_type: Optional[str] = None
    pre_launch_cmds: Optional[List[str]] = field(default_factory=list)
    wait: bool = False
    shared_folder: bool = True
    provision: Optional[ProvisionSteps] = None


@dataclass
class FilePushConfig:
    """Dataclass for file push configuration."""

    instance_name: str
    source: str
    target: str
    uid: Optional[int] = None
    gid: Optional[int] = None
    mode: Optional[str] = None
    recursive: bool = False
    create_dirs: bool = False
    quiet: bool = False
