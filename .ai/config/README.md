# Agent Framework Configuration

`.config` defines how the Agent understands, discovers, validates, loads, and coordinates Skills.

It is Framework configuration, not a collection of development Skills.

## Responsibilities

- Agent identity and framework version
- Skill contract/schema
- Skill taxonomy
- Skill registry
- Skill loading rules
- Skill dependency rules
- Skill collaboration rules

## Principle

```text
.config
  ↓
defines how Skills work

skills/
  ↓
defines what the Agent can do
```

Configuration should remain small and declarative. Project-specific architecture knowledge belongs to the appropriate Skill-managed memory, not in this directory.
