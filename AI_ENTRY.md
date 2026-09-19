# AI_ENTRY

版本：5.1 中文版

# AI Agent 开发环境入口协议

## 作用

这是 AI Agent 进入项目时首先读取的入口文件。

负责：

-   初始化 AI 开发环境
-   加载 AI 规则
-   加载 Skill 规范
-   读取项目记忆
-   读取当前上下文
-   发现 Skill
-   调度 Workflow

# Agent 启动流程

每次进入项目时，必须按照以下顺序执行：

## 第一步：读取 AI 规则

读取：

.ai/config/AI_RULES.md

了解：

-   AI 工作原则
-   修改文件规则
-   交流规则

## 第二步：读取 Skill 规范

读取：

.ai/config/SKILL_BLUEPRINT.md

了解：

-   Skill 的标准格式
-   Skill 的职责边界
-   Skill 的输入输出要求

## 第三步：读取长期记忆

读取：

.ai/memory/

了解：

-   项目目标
-   长期设计决定
-   架构原则

## 第四步：读取当前上下文

读取：

.ai/context/

了解：

-   当前任务
-   当前开发状态
-   最近工作

## 第五步：扫描 Skill

扫描：

.ai/skills/

检查：

-   是否符合 Skill Blueprint
-   是否存在新增 Skill

## 第六步：更新 Skill 索引

生成或更新：

.ai/registry/SKILLS_INDEX.md

## 第七步：执行任务

根据用户需求：

-   选择 Workflow
-   调用 Skill
-   必要时调用 Tool

# Skill 使用规则

使用 Skill 前必须理解：

-   Skill 职责
-   输入要求
-   输出格式
-   修改权限

如果 Skill 信息不完整：

不要直接使用。

应该先完善 Skill。

# Memory 与 Context 规则

长期知识：

.ai/memory/

例如：

-   游戏方向
-   架构决定
-   核心设计原则

当前状态：

.ai/context/

例如：

-   正在开发什么
-   修改到哪里
-   当前问题

临时信息不能写入 Memory。

# 多项目规则

.ai 是通用 AI 开发环境。

可以复制到不同项目。

不要在入口文件中保存具体项目内容。
