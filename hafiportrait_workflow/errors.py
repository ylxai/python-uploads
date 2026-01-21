from __future__ import annotations


class WorkflowError(Exception):
    """Base error type for the workflow."""


class ConfigError(WorkflowError):
    """Raised when configuration is missing or invalid."""


class MissingApiKeyError(ConfigError):
    pass


class MissingEventIdError(ConfigError):
    pass


class MissingLastEventError(ConfigError):
    pass
