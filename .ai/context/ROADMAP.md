# Roadmap

下一阶段开发方向（Agent 能力演进路线，2026-10-08 由用户确定）。

目标：从「Agent 按人给的指令做单点任务」演进为「Agent 能发现能力、理解需求、创建内容、自修、演化」的完整闭环。

优先级：P0 必须做 → P1 → P2；P0 内按编号顺序推进。

## P0（必须）

### 1. Feature Registry —— 让 Agent 能发现能力

- 新增 `feature.yaml`（Registry），让 Agent 无需逐目录扫描 `Features/` 即可查询已有能力
  （stun、pickup、moving_platform、health、condition_gate、trigger_switch 等，当前 12 个）。
- 与现有 Framework 的关系定位：
  - 定位类比 skill-registry.yaml：只做发现索引，canonical metadata 仍在各 Feature 的 README.md，
    Registry 不复制接口细节，避免重复存储与失同步。
  - 入口挂接：agent.yaml framework 节新增 `feature_registry` 指向，与 skill_registry 并列。
  - 与 feature-development.md §1 Discovery「扫描 Features/ 目录读取 README」衔接：
    Registry 加速发现，README 仍是复用方式的 canonical 来源。
- 待定设计问题（实现前需确定）：
  - schema 字段：id、path、职责一句话、类别/标签（如 移动/数值/交互/逻辑）、依赖的其它 Feature
  - 注册方式：新增 Feature 时手动登记 or 由 Validator/工具校验一致性
  - Validator 是否扩展：Feature 目录与 Registry 双向一致性检查

### 2. Game Design Skill —— 让 Agent 理解需求

- 新 Skill（需求分析类）：把自然语言游戏需求转译为「Feature 复用清单 + 缺口清单 + 场景组合方案」。
- 输入对齐 Feature Registry 的输出；输出对齐 feature-development.md 的 Reuse or Build 分支。

### 3. Scene Composer —— 让 Agent 能创建内容

- 新 Skill：依据设计产物创建/组合场景（实例化 Feature 场景、连接信号、配置导出参数、写场景胶水）。
- 需内化既有约定：AD-002 组件组合、AD-004 组合契约、AD-005 同签名布尔契约与 binds 参数顺序、
  Round 8 结论（状态所有权归 Feature，Glue 只做连接不做仲裁）。

## P1

### 4. Runtime Debug Agent —— 让 Agent 能自修

- 运行期错误捕获 → 定位 → 修复 → 回归验证的闭环（Headless 跑场景/测试已是现成验证基座）。

### 5. Asset Intelligence —— 让 Agent 能处理资源

- 资源（图/音频/场景资产）的盘点、选择与接入；现有 `.ai/context/asset_manifest.json` 可作起点调研。

## P2

### 6. Feature Migration System —— 支持长期演化

- Feature 接口变更时对既有消费者（场景/测试）的迁移机制。

### 7. Multi-Agent Workflow —— 多角色协作

- Designer / Architect / Coder / QA Agent 分工协作，
  与 skill-collaboration.yaml、feature-development.md 的检查点体系对接。

## 执行约定

- 每个 P0 项开始前：先读 `.ai/workflows/feature-development.md` §1 Discovery 与
  `.ai/context/CURRENT_TASK.md`，并按 Framework 惯例记录新的 Architecture Decision。
- 涉及 Framework 结构变更（agent.yaml、Validator）时保持 Validator PASS 后才收尾。
