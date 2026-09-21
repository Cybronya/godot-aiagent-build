# Architecture Principles

## 目标
建立可理解、可验证、可演化的 Godot 项目架构。

## 原则
1. **Ownership First**：核心状态和能力必须有明确 Owner。
2. **Single Responsibility**：模块职责清晰，多个独立变化原因才考虑拆分。
3. **High Cohesion**：相关逻辑尽量聚合。
4. **Low Coupling**：跨模块依赖保持最小。
5. **Dependency Direction**：依赖指向稳定能力，禁止循环。
6. **Local Before Global**：局部问题优先局部解决。
7. **Explicit Communication**：跨模块使用明确 API、Signal/Event 或数据契约。
8. **Stable Data Ownership**：核心状态只有一个写入 Owner。
9. **Evidence-Based**：架构决策基于当前需求和实际依赖，而非过度抽象。

## Decision Rule
两个方案都可行时，优先考虑：
- 更清晰的 Owner
- 更少的 Module
- 更少的全局状态
- 更少的跨模块依赖
- 更容易验证的边界
