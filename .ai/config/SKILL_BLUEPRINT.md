# SKILL_BLUEPRINT

版本：2.0

# Skill定义

Skill是AI Agent的一项专业能力模块。

Skill负责：

-   专业知识
-   决策规则
-   工作方法

Skill不负责：

-   全局流程
-   文件执行
-   项目状态管理

# Skill目录结构

标准结构：

skill-name/

├── SKILL.md

├── references/

├── examples/

├── templates/

└── assets/

# SKILL.md要求

每个Skill必须包含：

## 1. Identity

定义：

-   Skill ID
-   名称
-   版本
-   分类

## 2. Registry Metadata

必须包含：

-   category
-   load_policy
-   dependencies
-   ownership

与：

skill_registry.yaml

保持一致。

## 3. Responsibility

必须说明：

负责：

-   xxx

不负责：

-   xxx

## 4. Trigger Conditions

定义：

什么时候应该调用该Skill。

## 5. Workflow

定义：

Skill内部工作流程。

标准：

理解任务

↓

检查Context

↓

读取References

↓

执行规则

↓

验证结果

↓

更新状态

## 6. References

用于存放：

-   规范文档
-   知识说明
-   技术资料

## 7. Examples

用于存放：

-   示例
-   正确案例

## 8. Templates

用于存放：

-   文件模板
-   代码模板

# Skill设计原则

## 单一职责

一个Skill只负责一个领域。

## 明确边界

必须定义：

负责什么

不负责什么

## 同级隔离

同级Skill默认互不干预。

## 显式依赖

依赖必须声明。

禁止：

隐藏依赖。

# Skill注册流程

创建Skill：

1.  创建目录

2.  编写SKILL.md

3.  创建references/examples/templates

4.  更新skill_registry.yaml

5.  验证路径和依赖
