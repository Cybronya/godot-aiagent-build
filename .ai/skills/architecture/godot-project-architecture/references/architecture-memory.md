# Architecture Memory

Architecture Memory stores durable project architecture knowledge managed by `godot-project-architecture`.

It is not a development diary and not a replacement for source code.

## Information Model

```text
Architecture Overview
    ↓
Architecture Index
    ↓
Decisions
    ↓
Patterns
```

The project chooses the physical Agent-owned storage location. The Skill defines the information model and lifecycle, not a mandatory `.ai/architecture/` directory.

## Overview

Records current modules, systems, ownership, major dependencies, global services and Autoloads.

## Index

Provides retrieval-oriented pointers to decisions, patterns and architecture areas.

## Decisions

Record explicit choices that constrain future architecture.

## Patterns

Record validated recurring architecture structures.
