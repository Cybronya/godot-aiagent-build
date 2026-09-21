# SKILL: godot-project-architecture

## Skill Identity

- Skill ID: `godot-project-architecture`
- Skill Name: Godot 项目架构
- Version: 1.3
- Category: `architecture`
- Load Policy: `conditional`

## Description

负责 Godot 项目的整体架构组织、模块边界、依赖关系、系统归属、Autoload 决策、功能放置和架构重构。

## Purpose

帮助 Agent 判断一个 Feature、System、Module、Scene、Script 或 Resource 应该属于哪里，以及它们之间应该如何依赖和演化。

## Responsibility

### Ownership

- project_architecture
- module_boundaries
- dependency_graph
- system_placement
- autoload_architecture
- feature_placement
- architecture_refactoring
- architecture_decisions
- architecture_memory

### Responsible For

- Analyze existing project architecture
- Define Module / System boundaries
- Determine Feature placement
- Determine Scene / Script / Resource architectural ownership
- Define dependency direction
- Define data ownership
- Evaluate Autoload usage
- Define cross-module communication boundaries
- Plan architecture refactoring
- Create and validate Architecture Decisions
- Maintain durable architecture knowledge
- Validate architectural consistency

### Not Responsible For

- Naming rules
- Concrete GDScript implementation
- Detailed Scene Node design
- Concrete specialist-system implementation
- Art assets
- Performance optimization
- Build and release
- General-purpose development logs

## Dependencies

### Required

- `godot-development-standard`

### Related

- `godot-scene-system`
- `godot-gdscript`
- `godot-character-system`
- `godot-gameplay-system`
- `godot-ui-system`
- `godot-animation-visual`
- `godot-data-resource`
- `godot-audio-system`
- `godot-debug-testing`
- `godot-performance`
- `godot-build-release`

## Architectural Boundary

`godot-development-standard` answers:

> What standards should the project follow?

This Skill answers:

> How should the project be organized, divided, connected, and evolved?

Specialist Skills answer:

> How should a specific system be implemented?

## Skill Hierarchy

This Skill belongs to the `architecture` Skill category and acts as an upstream decision layer.

```text
Agent
  ↓
Architecture Skills
  ↓
Foundation Skills
  ↓
System Skills
  ↓
Engineering / Validation Skills
```

Architecture decides placement, ownership, boundaries and dependencies. Specialist Skills decide implementation.

## Architecture Model

Distinguish:

- Project
- Module
- System
- Feature
- Scene
- Script
- Resource

A Module is an architectural concept, not necessarily a directory.

Directories describe physical organization. Modules describe responsibility and boundaries.

## Core Principles

1. Ownership First
2. Single Responsibility
3. High Cohesion, Low Coupling
4. Explicit Dependency Direction
5. Local Before Global
6. Stable Boundaries
7. Stable Data Ownership
8. Architecture Before Implementation
9. Architecture Decisions Are Constraints
10. Reuse Accepted Architecture Before Inventing New Architecture

Default dependency:

```text
Feature
  ↓
System
  ↓
Foundation
```

Avoid circular dependencies unless there is an explicit architectural reason.

Cross-module communication should use explicit boundaries:

- Public API
- Signals / Events
- Data / Resource Contracts
- Stable interfaces

Core runtime state should normally have one write Owner.

## Architecture Decision System

Architecture Decision (AD) is the persistent record of an important architectural choice.

Statuses:

- proposed
- accepted
- superseded
- rejected
- deprecated

Only accepted decisions are active constraints.

Priority:

```text
User Decision
    ↓
Accepted Project Architecture Decision
    ↓
Project Rules
    ↓
Skill Rules
    ↓
Default Architecture Rules
```

When a new requirement conflicts with an accepted decision:

1. Identify the conflict.
2. Identify affected ownership, modules, dependencies and lifetime.
3. Do not silently overwrite the decision.
4. Propose migration or replacement.
5. Request confirmation when required.
6. Preserve history.

## Architecture Memory

Architecture Memory is durable project architecture knowledge managed by this Skill. It is not another Skill and not a general development log.

Conceptual layers:

```text
Architecture Overview
    ↓
Architecture Index
    ↓
Architecture Decisions
    ↓
Architecture Patterns
```

The physical storage location is project-defined. Do not assume `.ai/architecture/` is mandatory.

Reuse order:

1. Architecture index
2. Relevant decisions
3. Relevant validated patterns
4. Architecture overview
5. Current project structure/code

Accepted Decisions are active constraints. Validated Patterns are reusable defaults. Unconfirmed assumptions must not become durable memory.

Create a Decision for durable ownership, module boundaries, dependency direction, Autoload, cross-module communication, data ownership or major architectural tradeoffs.

Create a Pattern only for a recurring architecture problem that has been successfully implemented and validated.

Pattern confidence:

- candidate
- validated
- deprecated

Only validated Patterns are default reusable architecture.

When architecture changes:

1. Update overview.
2. Update index.
3. Supersede old decisions instead of deleting them.
4. Add replacement decisions where required.
5. Update pattern validation when evidence changes.

## Trigger Conditions

Use when:

- Creating a Godot project
- Adding a Module or System
- Adding a large Feature
- Changing Module responsibilities
- Changing System dependencies
- Adding/removing/changing an Autoload
- Sharing state across modules
- Large migrations
- Architecture refactoring
- Circular dependencies
- Responsibility drift
- Reviewing Architecture Decisions
- Determining Feature placement
- Searching architecture memory

## Input Contract

需要输入：

- 当前任务目标与约束
- 当前项目结构
- 现有 Module、System、Feature 及其边界
- Godot Development Standard
- Architecture Memory 中的相关 Overview、Index、Decisions 与 Patterns
- 已接受且可能受影响的 Architecture Decisions
- 当前相关 Scene、Script、Resource 与 Autoload 信息

如果关键架构信息不足：

1. 明确缺失的信息。
2. 优先从项目结构和 Architecture Memory 获取。
3. 无法确认时不得把推测当作已接受架构事实。
4. 涉及高风险架构变更时请求用户确认。

## Workflow

1. Understand Task
2. Load Development Standards
3. Search Architecture Memory
4. Analyze Existing Architecture
5. Determine Ownership
6. Determine Placement
7. Analyze Dependencies
8. Evaluate Autoload
9. Check Architecture Decisions
10. Produce Architecture Decision
11. Execute
12. Validate
13. Preserve Durable Decisions
14. Update Architecture Memory when required

## Failure Handling

### Information Insufficient

- Identify missing architectural context.
- Search available project architecture information and memory.
- Do not invent durable architecture facts.
- Request user clarification when the missing information changes ownership, boundaries, dependencies, or Autoload decisions.

### Architecture Decision Conflict

- Identify the conflicting accepted Decision.
- Preserve the existing Decision history.
- Propose a replacement or migration path.
- Request confirmation when the accepted Decision must change.

### Ownership Conflict

- Do not silently take ownership from another Skill.
- Identify the responsible Skill and required handoff.
- Preserve the architectural boundary.

### Dependency or Circularity Risk

- Stop execution of the affected architectural change.
- Re-evaluate dependency direction and ownership.
- Propose a corrected dependency model before implementation.

### High-Risk Refactor Failure

- Do not continue destructive changes.
- Preserve the last known valid architecture state where possible.
- Report affected artifacts, unresolved issues, and rollback or migration steps.

## Output Contract

```text
Architecture Decision:
Module Changes:
Dependency Changes:
Autoload Changes:
File Placement:
Architecture Decision Changes:
Memory Search:
Relevant Decisions:
Relevant Patterns:
Architecture Reuse:
Memory Files Updated:
Validation Result:
Remaining Issues:
```

If no durable change is required:

```text
Memory Update: None
```

## Validation

### Quick Check

For local/small changes:

- ownership is clear
- placement is coherent
- dependency direction is valid
- no unnecessary Autoload
- no accepted decision is violated

### Full Review

For new Modules/Systems, cross-module Features, Autoload changes, large refactors or core AD changes:

- module boundaries
- dependency graph
- ownership
- lifecycle
- global state
- communication
- accepted decisions
- memory consistency

Result: `PASS`, `WARNING`, or `FAIL`.

## Refactor Risk

Low:
- docs
- local module changes
- small dependency changes

Medium:
- moving a System
- changing module boundaries
- changing multiple dependencies

High:
- removing core modules
- changing core ownership
- changing core Autoloads
- large migrations
- changing core dependency direction

Workflow:

```text
Analyze
  ↓
Dependency Model
  ↓
Target Architecture
  ↓
Migration Plan
  ↓
Execute
  ↓
Validate
  ↓
Update Architecture Decisions
```

## Permission Model

Allowed:
- Analyze/propose architecture
- Create architecture documentation
- Create Decisions in authorized scope
- Adjust dependencies in authorized scope
- Update architecture memory

Requires confirmation:
- Remove core modules
- Change core ownership
- Remove/replace core Autoloads
- Large migrations
- Change accepted core Decisions

Prohibited:
- Bypass boundaries without justification
- Delete core logic without confirmation
- Add Autoload to hide unclear ownership
- Silently overwrite accepted Decisions
- Redefine another Skill's specialist responsibilities

## Skill Collaboration

This Skill has a required dependency on `godot-development-standard`.
The related Skills listed in the canonical `Dependencies` section are collaboration targets, not required dependencies.

Architecture decisions remain authoritative for placement, ownership, boundaries, dependency direction and Autoload decisions. Specialist Skills implement within those boundaries.

## Memory Interaction

Read:
- confirmed module boundaries
- long-term Decisions
- Autoload decisions
- dependency direction
- data ownership
- validated Patterns

Write:
- stable long-term Decisions
- validated reusable Patterns
- architecture overview
- retrieval index

Do not write temporary solutions, routine logs, tests or unconfirmed assumptions.

## References

- `references/architecture-memory.md`
- `references/memory-retrieval.md`
- `references/decision-lifecycle.md`
- `references/pattern-lifecycle.md`

## Templates

- `templates/architecture-overview-template.md`
- `templates/architecture-index-template.md`
- `templates/architecture-decision-template.md`
- `templates/architecture-pattern-template.md`

## Examples

- `examples/architecture-memory-example.md`
- `examples/architecture-change-example.md`
