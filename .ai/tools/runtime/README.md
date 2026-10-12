# Runtime Playtest & Self-Repair Tools

Phase 1.6 —— 在「静态验证」之后补上「真实运行 → 观测 → 诊断 → 修复 → 复验」的能力层。

## 1. 定位

```text
Gameplay Generation
        ↓
Static Validation（Validator：Project / Feature / Scene / Gameplay）
        ↓
Runtime Launch        run_scene.py / run_project.py
        ↓
Runtime Observation   exit code / duration / stdout / stderr / parsed events
        ↓
Failure Diagnosis     diagnose_runtime.py
        ↓
Repair Plan           repair_plan.py
        ↓
Apply Repair          repair_engine.py（由 self_repair.py 调度）
        ↓
Re-validation         repair_engine.static_validation + Validator
        ↓
Runtime Playtest      重跑，直到 PASS 或达到 max_repair_attempts
```

Runtime Playtest **不替代** Validator：

| 层 | 负责 | 不负责 |
|---|---|---|
| Validator | 静态正确性（结构 / 契约 / 组合 / 循环闭合） | 能否真实运行 |
| Runtime Runner | 运行与观测 | 判定与修复 |
| Diagnosis | 分类与定位 | 修改项目 |
| Self Repair | 最小修改 + 回滚 | 静态规则、Feature 实现 |

## 2. 工具

| 文件 | 职责 |
|---|---|
| `run_scene.py` | 启动 Godot（headless）运行指定 Scene，产出 runtime_result |
| `run_project.py` | 运行项目主场景（`project.godot` 的 `run/main_scene`） |
| `capture_output.py` | 解析 Godot 输出：ERROR / SCRIPT ERROR / WARNING + script/line/patterns |
| `runtime_result.py` | runtime_result 契约、status 语义、契约读取、Godot 定位、日志落盘 |
| `diagnose_runtime.py` | 错误分类（12 类）、likely_cause、related_feature / scene、confidence |
| `repair_plan.py` | Repair Plan 构建 + 修复安全策略（安全边界唯一权威） |
| `repair_engine.py` | 场景解析、节点候选评分、单点字面量替换、静态验证、回滚原语 |
| `self_repair.py` | 修复控制器：最大尝试次数、进度判定、回滚、修复历史 |
| `tests/` | Runtime Playtest 与 Self-Repair 回归测试（含 fixtures） |

Validator 侧配套：

| 文件 | 职责 |
|---|---|
| `.ai/tools/validator/check_runtime.py` | Validator 第 5 阶段：Runtime Validation（只判定，不修复） |

契约与 Schema：

- `.ai/config/runtime-playtest.yaml` —— timeout / max_repair_attempts / fail_on_error / repair_safety
- `.ai/context/runtime_result_schema.yaml` —— runtime_result
- `.ai/context/repair_plan_schema.yaml` —— repair plan

## 3. 常用命令

```bash
# 1. 运行单个场景（Test 1 的等价命令）
python .ai/tools/runtime/run_scene.py --project . --scene res://Scenes/EnemyBasic.tscn --timeout 30

# 2. 运行项目主场景
python .ai/tools/runtime/run_project.py --project .

# 3. 诊断已有结果
python .ai/tools/runtime/diagnose_runtime.py runtime_result.json --out diagnosis.yaml

# 4. 自动修复闭环（最大 3 次尝试）
python .ai/tools/runtime/self_repair.py --project . --scene res://Scenes/EnemyBasic.tscn --max-attempts 3

# 5. Runtime Validation（Validator 第 5 阶段）
python .ai/tools/validator/check_runtime.py runtime_result.json
python .ai/tools/validator/check_runtime.py --project . --scene res://Scenes/EnemyBasic.tscn

# 6. 回归
python .ai/tools/runtime/tests/test_runtime_playtest.py
python .ai/tools/runtime/tests/test_self_repair.py
```

退出码：`0` = PASS；`1` = FAIL / TIMEOUT / CRASH；`2` = 输入错误。

## 4. status 语义

| status | 判定条件 |
|---|---|
| `PASS` | 无解析错误、`exit_code == 0`、未超时 |
| `FAIL` | 解析出 error 事件（`fail_on_error: true`），或仅因 warning 判失败 |
| `TIMEOUT` | 超过 `runtime_playtest.timeout` 被强杀（优先于 FAIL / CRASH） |
| `CRASH` | 非 0 退出码且输出中没有可解析错误 |

Godot 场景通常不会自行退出，因此 Runner 使用 `--quit-after <run_frames>`（默认 60 帧）
让场景在跑完 `_ready` 与若干物理帧后正常结束；超时只用于「场景卡死」的情况。

## 5. 错误分类

`scene_load_error` / `script_error` / `node_not_found` / `resource_missing` / `signal_error` /
`null_instance` / `invalid_property` / `invalid_method` / `parser_error` / `timeout` / `crash` /
`unknown_runtime_error`。

分类规则是确定性的（`diagnose_runtime.CLASSIFY` 规则表 + `capture_output.PATTERNS` 事实），
无法判断时输出 `unknown_runtime_error`，禁止编造原因。`likely_cause` 只来自固定映射表。

## 6. 自动修复边界

当前**唯一**的确定性修复策略：

```text
node_not_found + 唯一可定位的硬编码节点路径字面量
    -> 在场景真实节点中按名称相似度选唯一候选
    -> 把出错字面量替换为正确的相对节点路径
```

硬约束：

- 只修改「报错脚本 / 被验证场景 / 相关 Feature 内文件」；每次尝试一个文件、一处字面量。
- 禁止修改 `.ai/**`、`addons/**`、`project.godot`；禁止删除 Feature / Scene。
- 字面量在文件中不唯一时拒绝修改（避免误伤）。
- 候选置信度低于 high 时默认不修（`--allow-medium` 才接受 medium）。
- 修复后必须静态验证 + 重跑；**修复无效或引入新错误立即回滚**。
- 其它分类（`parser_error` / `resource_missing` / `timeout` / `script_error` …）输出
  `repairable: false` + reason，交回人工或上游 Skill。

## 7. 产物

| 路径 | 内容 |
|---|---|
| `.ai/memory/runtime-logs/` | 每次运行的 stdout / stderr / result 快照（`save_logs`） |
| `.ai/memory/runtime-repairs/repair-00N.yaml` | 每次修复尝试：attempt / timestamp / error / diagnosis / changed_files / validation_result / runtime_result |
| `.ai/memory/DECISIONS.md` | 只有长期架构经验才写在这里；普通运行期错误不进入 |

## 8. 测试 fixture

`.ai/tools/runtime/tests/fixtures/` 下每个目录都是一个**独立的最小 Godot 项目**，
用于制造确定性错误。所有测试都会把 fixture 复制到临时目录后再运行，
保证不修改仓库、不依赖 `.godot` 缓存，也保证修复测试可重复执行。
