# AI_RULES

版本：5.2


# AI Agent 行为规则


## 1. 核心职责

AI Agent负责：

- 理解用户需求
- 分析项目状态
- 调用正确Skill
- 遵循项目规范
- 执行开发任务


AI Agent不是：

- 随意修改项目结构的自动程序
- 未经确认的架构决策者



# 2. 项目文件职责划分


## AI_ENTRY.md

负责：

- Agent启动流程
- 环境加载顺序
- 系统入口协议


## AI_RULES.md

负责：

- Agent行为约束
- 权限规则
- 工作原则


## SKILL_BLUEPRINT.md

负责：

- Skill设计规范
- Skill结构标准


## skill_registry.yaml

负责：

- Skill索引
- Skill发现
- Skill关系管理


## SKILL.md

负责：

- 单个Skill能力定义


## Workflow

负责：

- 任务流程编排


## Tool

负责：

- 实际执行动作



# 3. Skill发现规则


Agent必须通过：

.ai/registry/skill_registry.yaml


发现Skill。


禁止：

- 假设Skill存在
- 绕过Registry直接调用Skill


Skill加载流程：

Registry

↓

SKILL.md

↓

references/examples/templates



# 4. Skill隔离规则


同级Skill默认互相独立。


Skill之间通过：

- dependencies
- ownership


建立关系。


禁止：

- 修改其他Skill负责领域
- 覆盖其他Skill规则
- 创建隐式依赖



# 5. 修改权限


Agent可以：

- 修改用户明确指定的文件
- 创建必要开发文件
- 提供修改建议


Agent需要确认：

- 修改核心架构
- 删除重要文件
- 修改Registry
- 修改规则文件



# 6. 质量要求


所有开发结果需要：

- 符合项目规范
- 可维护
- 可扩展
- 可复用


优先：

稳定性 > 复杂度

清晰性 > 技巧性
