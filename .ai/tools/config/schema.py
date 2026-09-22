"""Declarative structural contracts for Framework configuration files.

This module validates configuration shape before semantic validation runs.
It is intentionally small: YAML structure belongs here; framework meaning
belongs to the validator.
"""
from __future__ import annotations

from typing import Any


TYPE_NAMES = {
    "mapping": dict,
    "list": list,
    "string": str,
    "integer": int,
    "boolean": bool,
}


CONFIG_SCHEMAS = {
    "agent": {
        "root": "framework",
        "required": ["framework"],
        "types": {"framework": "mapping"},
    },
    "rules": {
        "root": "framework",
        "required": ["framework"],
        "types": {"framework": "mapping"},
    },
    "schema": {
        "root": "schema",
        "required": ["schema", "required", "identity", "metadata", "operational_contract",
                     "dependencies", "registry_contract", "rules"],
        "types": {
            "schema": "mapping",
            "required": "list",
            "identity": "mapping",
            "metadata": "mapping",
            "operational_contract": "mapping",
            "dependencies": "mapping",
            "registry_contract": "mapping",
            "rules": "list",
        },
    },
    "types": {
        "root": "taxonomy",
        "required": ["taxonomy", "types", "rules"],
        "types": {"taxonomy": "mapping", "types": "mapping", "rules": "list"},
    },
    "registry": {
        "root": "registry",
        "required": ["registry", "skills"],
        "types": {"registry": "mapping", "skills": "list"},
    },
    "loading": {
        "root": "loading",
        "required": ["loading"],
        "types": {"loading": "mapping"},
        "nested": {
            "loading.version": "integer",
            "canonical_source": "mapping",
            "canonical_source.rule": "string",
            "policies": "mapping",
            "policies.required": "mapping",
            "policies.conditional": "mapping",
            "policies.optional": "mapping",
            "policies.required.behavior": "list",
            "policies.conditional.behavior": "list",
            "policies.optional.behavior": "list",
            "selection_order": "list",
            "rules": "list",
        },
    },
    "dependency": {
        "root": "dependency",
        "required": ["dependency", "relationship_types", "resolution", "validation", "category_direction"],
        "types": {
            "dependency": "mapping",
            "relationship_types": "mapping",
            "resolution": "list",
            "validation": "mapping",
            "category_direction": "mapping",
        },
    },
    "collaboration": {
        "root": "collaboration",
        "required": ["collaboration"],
        "types": {"collaboration": "mapping"},
        "nested": {
            "collaboration.version": "integer",
            "principle": "mapping",
            "principle.description": "string",
            "ownership": "mapping",
            "workflow": "mapping",
            "handoff_rules": "list",
            "output": "mapping",
            "output.each_skill_should_report": "list",
        },
    },
}


def _get(data: dict[str, Any], path: str):
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]
    return current, True


def validate_structure(data: Any, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Expected YAML mapping at root"]

    root = schema["root"]
    if root not in data:
        return [f"missing root key {root!r}"]

    for path in schema.get("required", []):
        if path not in data:
            errors.append(f"missing required key {path!r}")

    for path, type_name in schema.get("types", {}).items():
        value, exists = _get(data, path)
        if not exists:
            continue
        expected = TYPE_NAMES[type_name]
        if type_name == "integer":
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, expected)
        if not valid:
            errors.append(f"{path}: expected {type_name}, got {type(value).__name__}")

    for path, type_name in schema.get("nested", {}).items():
        value, exists = _get(data, path)
        if not exists:
            errors.append(f"missing required key {path!r}")
            continue
        expected = TYPE_NAMES[type_name]
        if type_name == "integer":
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, expected)
        if not valid:
            errors.append(f"{path}: expected {type_name}, got {type(value).__name__}")

    return errors
