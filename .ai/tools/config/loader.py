"""Framework configuration loader.

The loader owns YAML parsing and structural normalization. Validators consume
its output instead of re-discovering YAML hierarchy ad hoc.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigStructureError
from .schema import CONFIG_SCHEMAS, validate_structure


def load_config(path: Path, kind: str) -> tuple[dict[str, Any], list[str]]:
    if not path.is_file():
        return {}, [f"Missing config file: {path}"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {}, [f"Invalid YAML: {path}: {exc}"]

    schema = CONFIG_SCHEMAS.get(kind)
    if schema is None:
        raise ConfigStructureError(f"Unknown config schema kind: {kind}")

    errors = validate_structure(data, schema)
    return data, [f"{path}: {error}" for error in errors]


def normalize_behavior(value: Any) -> dict[str, Any]:
    """Normalize the framework's list-of-mappings behavior syntax."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        merged: dict[str, Any] = {}
        for item in value:
            if not isinstance(item, dict):
                raise ConfigStructureError(
                    "behavior entries must be mappings"
                )
            merged.update(item)
        return merged
    raise ConfigStructureError("behavior must be a mapping or list of mappings")
