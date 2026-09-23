# Agent Framework Configuration

`.ai/config` defines how the Agent understands, discovers, validates, loads, and coordinates Skills.

It is Framework configuration, not a collection of development Skills.

## Responsibilities

- Agent identity and Framework version
- Skill contract/schema
- Skill taxonomy
- Skill registry and discovery
- Skill loading rules
- Skill dependency rules
- Skill collaboration rules

## Principle

```text
.ai/config
  ↓
defines how Skills work

.ai/skills/
  ↓
defines what the Agent can do

.ai/tools/validator/
  ↓
checks whether the Framework currently satisfies its contracts
```

Configuration should remain small and declarative. Project-specific architecture knowledge belongs to the appropriate Skill-managed memory, not in this directory.

The Validator is intentionally separate from configuration and is executed only when the Agent is asked to perform a Framework/Skill validation.
