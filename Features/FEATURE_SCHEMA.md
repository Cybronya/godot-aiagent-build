# Feature Metadata Contract

Feature metadata (`feature.yaml`) is the machine-readable discovery layer for Agent.

## Purpose

Feature README explains humans usage.
Feature metadata explains Agent selection and composition.

## Required fields

```yaml
id: feature-id
version: 1
category: gameplay

description: short explanation

provides:
  - capability

requires:
  nodes:
    - Node

interfaces:
  methods:
    - public_method
  signals:
    - public_signal

validation:
  tests:
    - test_file
```

## Design rules

- Feature owns its internal state.
- Metadata describes public contracts, not implementation details.
- Scene composition should depend on provided capabilities.
- Missing metadata must not prevent existing Features from running during migration.
