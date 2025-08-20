"""
Custom exceptions for Incant.
"""

from typing import Optional


class IncantError(Exception):
    """Base exception for all Incant errors."""


class ConfigurationError(IncantError):
    """Raised when there's an issue with configuration loading or parsing."""


class InstanceError(IncantError):
    """Raised when there's an issue with instance operations."""


class ProjectError(IncantError):
    """Raised when there's an issue with project operations."""


class ProvisioningError(IncantError):
    """Raised when there's an issue with provisioning operations."""


class IncusCommandError(IncantError):
    """Raised when an Incus command fails."""

    def __init__(self, message: str, command: Optional[str] = None, stderr: Optional[str] = None):
        super().__init__(message)
        self.command = command
        self.stderr = stderr
