# Feature Development Workflow

本 Workflow 定义 Feature 开发的顺序、分支与检查点。

职责边界：

- Workflow：顺序、分支、检查点
- Skill：专业规则与实现方式
- Feature：项目实际可复用实现
- Memory：项目决策与经验

本文件不复制任何 Skill 的专业规则。

## 0. 适用范围

当且仅当任务属于 Feature Development（新增可复用实现单元，或需要固化为 Feature 的功能性工作）时进入本 Workflow。

普通 Bug Fix、配置调整、简单修改等任务走相关 Skill 自身的工作流，不强制进入本流程，也不强制 Finalization 为 Feature。

## 1. Discovery（任务开始时必须执行）

按顺序检查并形成现状简报：

1. 当前项目结构（目录组织、入口、实体）
2. Architecture Memory（已接受的 Decisions、validated Patterns、既有约定）
3. 已有 Features（扫描 Features/ 目录，读取各 Feature 的 README）
4. 与任务相关的 Skills（按 skill-loading.yaml 的 selection_order 取最小集合）
5. 待再评估的胶水：是否存在此前判定为「暂不 Feature 化」的场景级组合逻辑，其记录的提升条件是否已经成熟（见相关 AD）

禁止跳过 Discovery 直接实现。

## 2. 判断是否属于 Feature Development

依据 Discovery 简报与任务目标判断：

- 是 → 进入第 3 节
- 否 → 进入「普通任务最小路径」，完成后直接 Finish，不进入本 Workflow §3 之后的步骤

### 普通任务最小路径（No 分支）

普通任务不允许无验证收尾，最小步骤为：

1. Implementation：按相关 Skill 的工作流实现
2. Verification：至少覆盖被修改行为的项目级验证；修改涉及已有 Feature 时，必须附带该 Feature 的回归验证
3. Context / Memory：按需更新，无新信息时明确跳过
4. Finish：报告结果；不进入 Finalization

## 3. Reuse or Build（必须显式分支）

复用对象不止 Feature。Discovery 简报必须核对三类既有资产：

- **Feature / implementation reuse**：已有 Feature 的实现与公开接口
- **Architecture Decision / constraint reuse**：已接受的 AD 直接作为约束应用，不重新论证
- **Memory / engineering knowledge reuse**：Memory 与 Context 中已验证的工程经验（如测试陷阱、环境事项）

Reuse or Build 分支判断本身只针对「是否需要新实现」；规则与经验的复用不改变分支结果，但直接决定实现方式。

依据 Discovery 简报判断，不得凭空假设：

- 存在可覆盖任务需求的 Feature → Reuse 分支
- 不存在 → Build 分支
- 部分可复用 → 允许「Reuse 为主 + Build 补缺」，但两个部分都必须走完各自分支的验证

## 4. Implementation / Composition

### Reuse 分支

1. 只依赖 Feature 的公开接口（场景、导出参数、脚本 API），不复制内部实现
2. 项目侧差异通过配置与实例化参数表达
3. 完成接入后必须执行被复用 Feature 的回归验证

### Build 分支

1. 按 skill-collaboration.yaml 的 architecture_first / local_implementation 确定 Skill 序列
2. 未验证的实现不得视为完成
3. 放置、边界、依赖方向、跨模块协作涉及架构决策时，必须记录 Architecture Decision

## 5. Verification

- Feature 自身验证（随 Feature 交付、可重复执行）
- 项目级集成验证（Feature 接入项目后的行为验证）
- 两级验证全部通过，才允许进入 Finalization
- 验证失败时：分析原因 → 修复 → 重新验证，直至结果稳定；失败与修复过程记入 Context

## 6. Finalization（固化检查）

全部满足才能固化为正式 Feature：

- [ ] 自包含：实现、场景与验证随 Feature 目录一起交付
- [ ] 职责清晰：单一职责，符合 development-standard 的结构规则
- [ ] README：说明复用方式与依赖（需要的动作/参数/接口）
- [ ] 验证：存在可重复执行的验证
- [ ] Architecture Decision：涉及架构决策的已记录（引用编号）

## 7. Memory / Context Update

- 新的持久约束 → Architecture Memory
- 任务状态 → Context
- 复用结论、放置规则变化 → 同步受影响的 Skill references
- 工程经验与踩坑记录（语言/工具陷阱等）→ Context，不进入 Architecture Memory

Memory Update: None 也是合法结果。
