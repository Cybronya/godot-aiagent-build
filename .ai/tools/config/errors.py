"""Shared configuration validation errors."""

from __future__ import annotations


class ConfigError(Exception):
    """A configuration file is unreadable or structurally invalid."""


class ConfigStructureError(ConfigError):
    """A configuration file violates its declared structural contract."""
