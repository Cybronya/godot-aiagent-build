# 当前任务

> 历史实验档案（Round 5 → 8 全部结论，含 Siege Gate 状态所有权、Round 7 Do Not Reuse、
> 测试证据与后续处置记录）已归档至 `.ai/memory/HISTORY.md`。

## 当前状态

Phase 1.25（Semantic Orchestration Traces & Event-Level Regression Coverage）**已完成并实测**（未 commit）。

1. **waves 语义事件（v1 加性扩展，schema_version 仍为 1）**：LevelOrchestrator 在真实
   转换边界新增三种事件——`wave_started`（_start_wave，data: wave/total/enemies）、
   `wave_cleared`（_advance_wave，_traced_cleared_wave 幂等守卫）、`exit_unlocked`
   （exit_door.set_open(true) 边界）。真实捕获 trace 从 2 事件升至 7 事件语义链：
   started→wave0→clear→wave1→clear→exit_unlocked→victory。
2. **回放规则**：波次事件仅限 waves 模式（wave_event_outside_waves_mode）；索引递增
   与清空约束（wave_start_before_clear / wave_start_out_of_order / wave_clear_mismatch）；
   exit_unlocked 至多一次且须在全部波次清空后（duplicate_exit_unlock /
   exit_unlocked_before_final_clear）；waves 胜利前须清完全部波次
   （victory_before_all_waves_cleared）；data.total 首现后固定（wave_total_mismatch）。
   **向后兼容**：旧 trace（无波次事件）回放行为不变——四条既有基线全部验证仍可回放。
3. **holdout 审计结论**：开始与计时是同一原子转换（orchestration_started reason=holdout），
   完成已有 level_victory(survive_duration)——按「不虚构不存在的状态」原则不新增事件，
   holdout 基线保持 v1。boss 基线零重录。
4. **基线**：waves 经 candidate→review→apply 显式重批为 **v2**（7 事件）；boss/holdout
   不变。批准记录含指纹与来源。
5. **测试**：回放器 R44–R57（14 项新规则，58/58）；比较器 U57–U63（分层语义：回放非法
   突变 = INVALID_TRACE、回放合法语义变化 = REGRESSION，均 exit 1；64/64）；e2e 独立
   **171/171 PASS**（T5a–T5d 四模式逐事件比较，含 waves v2）；全量单命令 79 项中
   78 PASS（e2e 超时覆盖提至 1800s 后通过；唯一失败 = 环境守卫杀 cross_layer 清理阶段，
   其断言全过）；Godot 八个编排专项全部 exit 0（行为兼容）；unified 36、cross_layer 66、
   composite 17、level_planner 134；
   validate.py 0 error / 17 warning（基线不变）。

## 下一阶段方向

路线图已记录于 `.ai/context/ROADMAP.md`（P0：Feature Registry / Game Design Skill / Scene Composer；
P1：Runtime Debug Agent / Asset Intelligence；P2：Feature Migration System / Multi-Agent Workflow）。
P0-1 Feature Registry（Metadata Pipeline + Composition Planner）与
P0-3 Scene Composer 与 P1 前置的 Gameplay Loop Composer 均已完成；下一任务候选：P0-2
Game Design Skill、提交成果（Phase 1.5 全链成果待 commit），
或直接串联「自然语言 → Gameplay Blueprint → 全部实体场景 → 验证」的多实体生成演示。

P1-4 Runtime Debug Agent 已由 Phase 1.6（AD-010）覆盖（运行期错误捕获 → 定位 → 修复 → 复验闭环）。

Phase 1.21 之后的建议（按价值排序）：

1. **阶段条件扩展**：在 `clear_enemies` / `defeat_boss` 之外增加可校验的条件（如 Boss 血量阈值、
   限时生存阶段），仍由 `LevelConfig` 声明、`LevelOrchestrator` 执行，不引入通用状态机框架。
2. **Boss 生成链路产物化**：让组合器/生成器输出可直接挂 `LevelHost` 的宿主（或在计划中
   声明宿主适配器入口），避免调用方手工挂载适配节点。
3. **交叉校验前移到 producer**：`build_boss_level` 接受 `plan` 后直接拒绝宿主根/实例不一致，
   不必等到 `check_level --plan`；同时把 `on_start` Boss 的“不参与宿主实例校验”写成显式策略。
4. **Holdout 生成器**（可选）：当前只手工编写 holdout 配置；若确有需求再扩 `generator_scope`，
   不为了对称性虚构能力。

## AD 候选（挂起，观察中）

当多个触发路径作用于同一个状态域时，应优先由该状态的 Feature 定义冲突语义，而不是让 Scene Glue 仲裁。
与既有 AD（002/005）方向一致，暂不升格；待出现第一个需要在 Glue 层仲裁的真实案例再评估。
