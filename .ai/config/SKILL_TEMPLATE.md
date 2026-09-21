# SKILL_TEMPLATE

版本：2.1

> 本模板是 Skill 的完整编写规范。
> skill-schema.yaml 定义机器验证的最低结构契约；本模板定义完整的 Skill 编写与运行契约。

# Skill Identity

## Skill ID

填写 Skill 唯一ID。

## Skill Name

填写 Skill 名称。

## Version

填写版本号。

## Category

必须与 skill_registry.yaml 保持一致。

必须来自 skill-types.yaml 定义的 Skill Category。

# Registry Metadata

用于同步 Registry。

## Load Policy

填写：

- required
- conditional
- optional

语义：

- required：Agent 正常运行或 Framework 要求时必须加载。
- conditional：当前任务匹配 Skill 的 Trigger 或 Responsibility 时加载。
- optional：按需或被明确请求时加载。

> experimental 不是 Load Policy。
> 如果未来需要表达 Skill 的成熟度，应使用独立的生命周期/状态字段。

## Dependencies

声明依赖 Skill。

## Ownership

定义本 Skill 负责领域。

------------------------------------------------------------------------

# Purpose

说明：

该 Skill 解决的问题。

------------------------------------------------------------------------

# Responsibility

## 负责

列出 Skill 管理范围。

## 不负责

明确禁止范围，避免职责冲突。

------------------------------------------------------------------------

# Trigger Conditions

定义：

什么时候应该调用该 Skill。

**Operational Contract：必填。**

------------------------------------------------------------------------

# Input Contract

定义：

Skill需要接收的信息。

**Operational Contract：必填。**

------------------------------------------------------------------------

# Workflow

标准流程：

1. 理解任务目标
2. 检查当前 Context
3. 读取 References
4. 执行 Skill 规则
5. 验证结果
6. 更新状态

**Operational Contract：必填。**

------------------------------------------------------------------------

# Output Contract

定义：

Skill完成后的输出格式。

**Operational Contract：必填。**

------------------------------------------------------------------------

# Validation

定义验证规则。

**Operational Contract：必填。**

## Validation Method

验证方式。

## Success Criteria

成功标准。

## Status Update

状态：

- PASS
- WARNING
- FAIL

------------------------------------------------------------------------

# References

存放：

- 技术规范
- 文档
- 设计资料

目录：

references/

------------------------------------------------------------------------

# Examples

存放：

- 示例
- 正确案例

目录：

examples/

------------------------------------------------------------------------

# Templates

存放：

- 文件模板
- 代码模板

目录：

templates/

------------------------------------------------------------------------

# Collaboration

## Dependencies

依赖的 Skill。

## Related Skills

相关 Skill。

## Communication Rules

规则：

同级 Skill 默认互不修改职责。

Skill之间通过：

- dependencies
- ownership

建立关系。

------------------------------------------------------------------------

# Tool Usage

定义：

需要调用的 Tool。

------------------------------------------------------------------------

# Memory Interaction

## Read

允许读取：

- 长期项目规则
- 架构决定

## Write

只保存长期有效信息。

禁止保存临时状态。

------------------------------------------------------------------------

# Failure Handling

定义：

- 错误识别
- 回退策略
- 用户确认节点

**Operational Contract：必填。**

------------------------------------------------------------------------

# Permission Model

定义：

允许执行：

- 创建文件
- 修改指定范围

需要确认：

- 修改核心架构
- 删除重要资源
- 修改 Registry

------------------------------------------------------------------------

# Skill Completion Report

完成后输出：

```text
Skill:

任务:

修改内容:

验证结果:

状态:

后续建议:
```

------------------------------------------------------------------------

# Notes

其他说明。
