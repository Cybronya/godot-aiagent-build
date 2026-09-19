# Skill Blueprint

版本：1.0

# 目的

定义 AI Skill 的统一规范。

Skill 是 AI 的专业能力模块。

# Skill 与其他模块关系

Skill：

负责思考和专业能力。

Tool：

负责执行具体程序。

Workflow：

负责组织工作流程。

Memory：

负责长期知识。

Context：

负责当前状态。

# Skill 必须包含内容

## 1. Metadata

必须包含：

-   名称
-   版本
-   描述
-   分类
-   能力列表
-   可处理任务
-   不可处理任务
-   状态

## 2. Identity

说明：

这个 Skill 是什么。

## 3. Purpose

说明：

为什么存在。

## 4. Responsibility

必须说明：

负责：

-   

不负责：

-   

避免 Skill 职责重叠。

## 5. Trigger Conditions

说明：

什么情况下调用。

## 6. Input Contract

说明：

执行需要什么输入。

如果信息不足：

必须询问。

## 7. Workflow

标准流程：

1.  理解任务
2.  查看 Context
3.  查看 Memory
4.  执行工作
5.  验证结果
6.  更新状态

## 8. Output Contract

输出：

-   修改内容
-   修改文件
-   测试结果
-   遗留问题

## 9. Permission Model

声明：

允许修改：

禁止修改：

## 10. Memory Interaction

说明：

哪些情况更新 Memory。

哪些情况只更新 Context。

## 11. Collaboration

说明：

需要配合哪些 Skill。

## 12. Tool Usage

说明：

需要调用哪些 Tool。

## 13. Failure Handling

说明：

遇到：

-   信息不足
-   文件错误
-   设计冲突

如何处理。
