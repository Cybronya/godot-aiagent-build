# Phase 1.62 执行前审计（以当前仓库为准）

审计时间：2026-11-04。审计人：Phase 1.62 执行 Agent。
所有结论均来自当前工作区的真实代码与文件实测，不引用历史报告作为事实来源。

---

## 1. Git 与工作区事实（实测）

- 分支：`master`；HEAD：`dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`
- `git status --porcelain`：**1016 条未提交修改** + 既有 code_library 删除（其他 Agent 迁移中）
- 审计结论：一切实现必须叠加在当前工作区之上；禁止任何 reset/checkout/restore/clean

## 2. 运行环境事实（实测）

| 项目 | 值 |
| --- | --- |
| Python | 3.12.10（CPython，`F:\Program Files\Python3.12\python.exe`）|
| Godot | `F:\Godot_v4.7-stable\Godot_v4.7-stable_win64_console.exe`（v4.7.0）|
| PyNaCl | 1.6.2（Ed25519 签名库可用）|
| cryptography | 未安装 |
| 测试框架 | 无 pytest；既有测试均为独立 Python 脚本（直接 `python test_xxx.py`）|
| CI / Secret / 外部密钥设施 | **不存在**。无 `.github/`、无 CI 配置、无 KMS、无容器编排 |
| 独立 Worker | **不存在**。执行器 = 本地 Python 进程（subprocess 调 Godot）|
| 操作系统 | Windows |

## 3. Phase 1.61 签名系统状态（实测）

Phase 1.61 签名系统完整且全部测试通过：

| 测试套件 | 结果 |
| --- | --- |
| test_provenance_core.py | **57 checks, 0 failures** |
| test_provenance_attacks.py | **32 checks, 0 failures** |
| test_evidence_signature.py | **16 checks, 0 failures** |

### 关键接口（可直接复用）

```
validator/provenance/
├── __init__.py          公共 API 导出
├── signature_schema.py  封套 schema、规范化序列化、结果词表
├── trust_store.py       外部信任根加载 + 密钥生命周期 ACTIVE/RETIRED/REVOKED
├── key_metadata.py      密钥身份 + scope 授权 + 私钥种子存取
├── signing.py           Ed25519 签名（build_envelope / sign_envelope / sign_object）
├── verification.py      fail-closed 验证管线 + 策略分级
└── provenance_cli.py    keygen / rotate / revoke / status / sign / verify
```

### 当前对象类型与 scope

| object_type | scope | 状态 |
| --- | --- | --- |
| baseline | approve_baseline | 已有 |
| evidence_bundle | issue_evidence | 已有 |
| holdout_dataset | seal_holdout | 已有 |

### 信任根路径

默认 `<user home>/.provenance_trust/<slug>/trust_root.json`（工作区外）。
环境变量覆盖：`PROVENANCE_TRUST_ROOT` + `PROVENANCE_REVOCATIONS`。

### 审计结论

Phase 1.61 **完好可用，密码学边界不被本阶段破坏**。本阶段应：
- 新增 `execution_attestation` object_type + `attest_execution` scope
- 复用签名基础设施，不另建密码学体系
- 私钥种子管理机制沿用 key_metadata.load_seed / write_seed

## 4. 执行入口审计（实测）

### 4.1 Evidence 生成入口

主入口：`.ai/tools/scene_composer/feature_behavior_evidence.py`

```
class BehaviorRun:
    __init__(feature, behavior, scene, run_id="", replay_index=0)

def _new_run_id(tag="") -> str:
    # 简单 uuid.uuid4().hex[:12]——仅用于采集目录命名，非全局唯一 Execution Identity

def _evidence_dir(run_id) -> str:
    # .ai/tmp/behavior/<run_id>/

def run_probe(contract, project_root, probe_path) -> dict:
    # 构造 subprocess: [godot, "--headless", "--path", project, "-s", probe,
    #                   "--contract=", "--result=", ...]

def verify_feature(feature_id, ...) -> list[BehaviorRun]:
    # 对每个声明 behavior，按 replay 次数循环执行，收集结果
```

### 4.2 Godot 启动

```
subprocess.run([godot_exe, "--headless", "--path", PROJECT_ROOT,
                "-s", "res://.ai/tools/scene_composer/probes/feature_behavior_probe.gd",
                "--contract=<json>", "--result=<path>",
                "--mode=<behavior>", "--action=<id>", ...])
```

### 4.3 Replay 流程

- `BehaviorRun` 记录每次 Godot 执行的 result.json 内容
- 默认 replay=2（两次独立执行，检查重放一致性）
- 结果保存在 `.ai/tmp/behavior/<run_id>/result.json`

### 4.4 现有 run_id 实现

`_new_run_id()` = `uuid.uuid4().hex[:12]`。**局限**：
1. 只是 UUID 前缀，不是完整 UUID
2. 只在 Evidence 生成流程内使用，Validator 侧独立生成
3. 不包含 execution_id / parent_run_id / 生命周期元数据
4. 不绑定 Environment / Source / Collector 指纹
5. 不进入签名消息

### 4.5 Artifact 路径

| 产物 | 位置 | 保护机制 |
| --- | --- | --- |
| result.json | `.ai/tmp/behavior/<run_id>/result.json` | Phase 1.57 路径约束 + SHA256 重算 |
| Evidence Bundle | 收集后写入 Evidence 目录 | SHA256 完整性 + Phase 1.61 签名 sidecar |
| 执行日志 | stdout/stderr 被采集 | 无独立签名 |

## 5. Artifact Cross-Validation 现状（Phase 1.57）

模块：`.ai/tools/validator/execution_artifacts.py`

```
class ArtifactResolver:
    # evidence_paths -> 真实产物路径（realpath + 授权根目录包含检查）
    # 拒绝：越界路径、..、符号链接逃逸、非 result.json 文件

def sha256_file(path) -> str
def cross_validate(resolver, record) -> dict:
    # 重算 result.json 摘要、核对执行标识/Feature/Behavior、重放次数、观测值一致性
```

**Phase 1.57 不做的**（本阶段补）：
- 不绑定 Run ID（只依赖 Evidence 内 evidence_paths 字段）
- 不验证 Artifact 属于同一次执行
- 不验证执行来源（执行器身份、环境、采集器）

## 6. Evaluator / Validator 接入点

### Validator 侧
```
validator/check_behavior_evidence.py:  Evidence Bundle + Artifact Cross-Validation
validator/validate.py:                --behavior-evidence 阶段入口
validator/execution_artifacts.py:     路径约束 + 摘要重算
validator/provenance/verification.py: 签名 sidecar 验证
```

### Evaluation 侧
```
evaluation/evidence_adapter.py:   load_verified() + evaluation_status()
evaluation/evidence_eval.py:      Mode A/B/C 运行 + 来源验证
evaluation/holdout_registry.py:   Holdout 数据集签名封存
```

## 7. 执行器与写权限边界

**当前真实状态**：

| 项 | 现状 |
| --- | --- |
| 执行器进程 | 本地 Python（subprocess 父进程）|
| 执行器与 Godot 关系 | 同一系统调用 subprocess |
| 执行器与项目代码关系 | 同一 Python 进程空间（import feature_behavior_evidence）|
| 执行器与信任根关系 | 信任根在 `<home>/.provenance_trust/`，Python 进程可读 |
| 执行器与工作区权限 | 同一管理员级权限 |
| 独立 Worker/CI/容器 | **不存在** |

**信任等级评估**：本阶段可实现 **LOCAL_ISOLATED**（本地隔离原型），但 **不具备** EXTERNAL_TRUSTED_RUNNER。

**诚实声明**：
- Phase 1.62 能证明"密码学签名 + 执行元数据"一致性
- 不能防御"管理员级攻击者同时改写工作区 + 替换 Godot + 伪造全部产物"
- 要达到 EXTERNAL_TRUSTED_RUNNER，需要：独立容器 / CI Runner / 远程 Worker + 密钥隔离 —— **本阶段不实现**

## 8. 当前缺失的 Phase 1.62 能力（零命中）

| 能力 | 搜索结果 |
| --- | --- |
| 全局唯一 Execution Identity | 无。只有 `_new_run_id()` 用于目录命名 |
| Run Manifest | 无 |
| Environment Fingerprint | 无 |
| Source Fingerprint（Git HEAD + 工作区状态摘要） | Evidence bundle 自报 `git_head`，非独立采集 |
| Collector Provenance（采集器代码摘要） | 无 |
| Execution Attestation（执行证明签发） | 无 |
| Attestation 验证入口 | 无 |
| Artifact-to-Run 绑定 | 无（Phase 1.57 不绑定 Run ID）|
| Attestation object_type + scope | 无（需新增到 signature_schema）|

## 9. 威胁模型对齐

**本阶段可防御**（LOCAL_ISOLATED 级别）：
- 修改 Run Manifest → 签名验证失败
- 替换 Godot result.json → Artifact 摘要不匹配 + Run ID 绑定断裂
- 修改 Replay → 重放一致性检查失败 + Run ID 绑定断裂
- 伪造 Collector Version → Collector Fingerprint 摘要不匹配
- 用 Evidence 签名代替 Attestation → scope 不匹配拒绝
- 跨 Run 产物混合 → Artifact-to-Run Binding 拒绝
- 重放旧 Attestation → 结合 Run ID 唯一性拒绝

**本阶段不能防御**（诚实声明，不夸大）：
- 管理员级攻击者同时改写工作区 + 替换 Godot + 伪造全部产物
- 攻击者控制独立执行器私钥
- 硬件级可信执行（TPM/SGX）

## 10. 本阶段实现边界（DEFERRED 清单）

| 能力 | 状态 |
| --- | --- |
| Run Identity（UUIDv4 + 完整生命周期）| **本阶段实现** |
| Environment Fingerprint | **本阶段实现** |
| Source Fingerprint（Git HEAD + 工作区）| **本阶段实现** |
| Collector Fingerprint | **本阶段实现** |
| Run Manifest | **本阶段实现** |
| Artifact-to-Run Binding | **本阶段实现** |
| Execution Attestation（本地原型）| **本阶段实现**（LOCAL_ISOLATED）|
| Attestation 独立 object_type + scope | **本阶段实现**（新增到 signature_schema）|
| Validator Attestation 验证 | **本阶段实现** |
| Evidence → Attestation 绑定 | **本阶段实现** |
| Evaluation Attestation 识别 | **本阶段实现** |
| 独立执行器 Worker/CI/容器 | **DEFERRED** |
| EXTERNAL_TRUSTED_RUNNER 等级 | **DEFERRED** |
| HARDWARE_ATTESTED 等级 | **DEFERRED** |

## 11. 审计回答任务书 §1 的 12 个问题

| # | 问题 | 回答 |
| --- | --- | --- |
| 1 | Phase 1.61 签名系统是否仍然正常？ | **是**。57+32+16 tests 全过 |
| 2 | 当前 Evidence 的生成入口在哪里？ | `scene_composer/feature_behavior_evidence.py::verify_feature()` |
| 3 | Godot 的真实启动入口在哪里？ | `run_probe()` 中 `subprocess.run([godot, "--headless", "--path", ..., "-s", probe])` |
| 4 | Replay 的生成过程在哪里？ | `verify_feature()` 中按 `replay` 参数循环调用 `run_probe()`，收集 `BehaviorRun` |
| 5 | Artifact 的生成与保存位置在哪里？ | `.ai/tmp/behavior/<run_id>/result.json`，由 Godot 探针写出 |
| 6 | 当前执行过程是否存在独立执行器？ | **否**。本地 Python 进程直接 import 采集器并 subprocess 调 Godot |
| 7 | 执行器与项目工作区是否处于不同写权限边界？ | **否**。同一管理员级权限 |
| 8 | 当前能否获得可信的执行器身份？ | **否**。无独立身份机制，只有 `_new_run_id()` 用于目录命名 |
| 9 | 当前是否存在 CI、容器或独立 Worker？ | **否**。全本机 |
| 10 | 当前是否能够保护执行器签名私钥不被项目代码读取？ | **部分**。Phase 1.61 签名密钥种子在 `<home>/.provenance_trust/`，Python 进程可读（同一用户），但不在工作区内 |
| 11 | 当前有哪些环境变量和运行参数会影响执行结果？ | GODOT_BIN（Godot 位置）、PROVENANCE_TRUST_ROOT（信任根）、PROVENANCE_REVOCATIONS（撤销覆盖）、--contract/--result 路径、--replay 次数 |
| 12 | 当前是否存在可以重放或伪造的执行元数据？ | **是**。`git_head`、`run_id`（只是目录名前缀）、采集器版本——全部自报，无独立采集 |

---

**审计完成，可进入设计与实现阶段。**

Phase 1.61 签名系统完好可用，本阶段应**加法式**在其之上构建，不破坏任何既有接口和测试。
