# AI_ENTRY

版本：5.2

# AI Agent 项目入口协议

## 作用

AI_ENTRY是Agent进入项目时首先读取的入口文件。

负责：

-   初始化AI环境
-   加载规则
-   发现Skill
-   加载Skill
-   调度Workflow
-   管理Agent行为

------------------------------------------------------------------------

# Agent启动流程

## 1. 加载基础规则

读取：

.ai/config/AI_RULES.md

获取：

-   AI行为规范
-   修改权限
-   工作原则

------------------------------------------------------------------------

## 2. 加载Skill规范

读取：

.ai/config/SKILL_BLUEPRINT.md

获取：

-   Skill结构规范
-   Skill设计标准
-   Skill输入输出规则

------------------------------------------------------------------------

## 3. 加载Skill Registry

读取：

.ai/registry/skill_registry.yaml

Registry负责：

-   Skill发现
-   Skill路径查询
-   Skill分类
-   Skill依赖关系
-   Skill状态管理

Agent必须通过Registry寻找Skill。

------------------------------------------------------------------------

# Skill加载流程

当任务开始：

1.  分析任务需要的能力。

2.  查询：

.ai/registry/skill_registry.yaml

3.  根据：

-   category
-   trigger_conditions
-   dependencies
-   ownership

选择Skill。

4.  加载：

.ai/skills/{skill-id}/SKILL.md

5.  根据Skill需求加载：

-   references
-   examples
-   templates

------------------------------------------------------------------------

# Skill架构规则

## 分类层级

foundation

基础规则。

architecture

架构设计。

system

游戏系统。

feature

具体功能。

optimization

优化。

------------------------------------------------------------------------

# Skill隔离规则

同级Skill默认互不干预。

禁止：

-   修改其他Skill负责领域
-   覆盖其他Skill规则
-   重复定义职责

关系通过：

-   dependencies
-   ownership

建立。

------------------------------------------------------------------------

# Registry规则

Agent可以：

-   读取Registry
-   检查Registry

Agent不能：

-   自动修改Registry

新增Skill必须经过确认。

------------------------------------------------------------------------

# Workflow规则

Workflow负责：

任务流程。

Skill负责：

专业能力。

Tool负责：

实际执行。

------------------------------------------------------------------------

# Memory与Context

memory:

长期项目知识。

context:

当前开发状态。

临时信息禁止写入memory。
