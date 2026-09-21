# Architecture Change Example

## Scenario

The project proposes moving Inventory from Player ownership to a global Inventory Autoload.

## Existing Decision

`AD-001`:

- Owner: Player
- Autoload: false

## Conflict

The change affects ownership, lifetime, dependency direction, global state, Save access and UI access.

## Required Process

1. Identify the conflict.
2. Explain architectural consequences.
3. Propose replacement architecture.
4. Request confirmation if required.
5. Create replacement Decision after acceptance.
6. Mark `AD-001` superseded.
7. Update architecture overview.
8. Update architecture index.

Never silently convert a local system into an Autoload merely to simplify access.
