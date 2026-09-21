# Architecture Memory Example

## Task

Add a player inventory.

## Memory Search

Search Inventory, Player, Gameplay, Ownership, Save and Autoload.

## Existing Decision

`AD-001` states that Player owns runtime inventory state.

## Reuse

Preserve Player ownership, Gameplay/Inventory placement, no global Inventory Autoload, public API and optional signals.

## Memory Update

If no new durable rule exists:

```text
Memory Update: None
```
