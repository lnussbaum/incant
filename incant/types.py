"""This module defines common types for incant."""

from typing import Any, TypeAlias, Union

InstanceDict: TypeAlias = dict[str, dict[str, Any]]

ProvisionStep: TypeAlias = Union[str, dict[str, Any]]
ProvisionSteps: TypeAlias = Union[list[ProvisionStep], str]
