# 当前任务

## 目标

执行《架构回收分析》Proposal：将两轮真实开发验证的实践反向沉淀为 Framework 规则（P1 Workflow / P2 Principles / AD 归宿统一 / P4 陈旧文档清理），不开发新的 Gameplay。

## 当前状态

已完成：四项修改全部落地，Validator PASS（0 errors / 0 warnings），入口链完整，diff 审查无越界。

## 修改文件

- `.ai/workflows/feature-development.md`：扩充为含适用范围判定的完整生命周期流程
- `.ai/config/framework-rules.yaml`：追加 Feature 一等单元、AD 单一归宿两条 principle
- `.ai/memory/DECISIONS.md`：声明唯一物理归宿，格式对齐实际 AD 字段
- `.ai/skills/architecture/godot-project-architecture/references/architecture-memory.md`：明确 template 仅为 information-model 指导
- `AI_ENTRY.md`：删除失效的 Legacy Registry 章节，重新编号

## 下一步

用一个新的真实开发任务验证 Framework 修改是否实际改变 Agent 行为。
