# Phase 1.68.3.1 — Phase 4: Scene Composer Eligibility Test Alignment Report

- 阶段：Phase 1.68.3.1 / Phase 4
- 日期：2026-11-11
- 基线 HEAD：`04f50636c7d3afb37a2a58454cb4ae16f1a38593`
- 执行范围：只修改 3 个测试文件；未修改生产逻辑、Feature 数据、Registry、Schema、Contract、Evidence/Attestation
- 最终判定：**PASS**

---

## A. Baseline

### A.1 Git 基线

| 项目 | 值 |
|---|---|
| HEAD | `04f50636c7d3afb37a2a58454cb4ae16f1a38593` |
| staged | `0` |
| dirty（Phase 4 开始时） | `1056` |
| Phase 1 快照 dirty | `1053` |
| Phase 1 快照时间 | `2026-11-10T23:08:56+08:00` |

说明：Phase 1 快照 dirty 为 1053；Phase 4 开始时为 1056，差额来自此前阶段生成的 3 份未跟踪报告，不是本次修改造成。Phase 4 没有覆盖、清理或回退任何既有 dirty 内容。

### A.2 目标测试修改前 SHA256

| 文件 | 修改前 SHA256 |
|---|---|
| `.ai/tools/scene_composer/tests/test_scene_composer.py` | `1e1f3ad3415a59bc7e2b0ff77cc62f43f613808780a2ec64b94741409ef9e1dd` |
| `.ai/tools/scene_composer/tests/test_feature_capability_pipeline.py` | `8aebea21658183ea614ab34b5a0e3feff54385b2f75872f78af8db652b7381fb` |
| `.ai/tools/scene_composer/tests/test_feature_capability_adoption.py` | `22bf81f794e6114168313e42b22fe5810360d55e23bbc2f775aa35373087b4f3` |

### A.3 修改后 SHA256

| 文件 | 修改后 SHA256 |
|---|---|
| `.ai/tools/scene_composer/tests/test_scene_composer.py` | `d0f3bbed23939ffee566f9fca5573f3f06bb0fcf71b9d3b35f5578bd89cf6872` |
| `.ai/tools/scene_composer/tests/test_feature_capability_pipeline.py` | `3c6f2fa1b35ec10d18310a3602e63329d6874f8b7738d460f25db8c856d53037` |
| `.ai/tools/scene_composer/tests/test_feature_capability_adoption.py` | `7b5c5f4518471f001fde0deeb7e6482c953484cfc3df61ae76d21caeffd46371` |

### A.4 受保护文件基线 SHA256

| 文件 | 修改前/基线 SHA256 | 最终 SHA256 |
|---|---|---|
| `.ai/context/feature_index.json` | `1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` | 同左 |
| `.ai/context/feature_graph.json` | `b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` | 同左 |
| `Features/FEATURE_SCHEMA.md` | `dca7c57accf7464ccd8f4919741a078c629cdbf661718440a8c5b31f01cb56fc` | 同左 |
| `.ai/context/behavior_protocol.yaml` | `d2a480b068559124bb51d74782b6ec2d33c29135573f9a9f39aa491559eea778` | 同左 |
| `.ai/tmp/p168/official/evidence/evidence_index.json` | `0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910` | 同左 |

Phase 1 快照提供的哈希清单：

- `.ai/tmp/p1683/baseline/features_sha256.txt`：265 个文件（包含全部 31 个 Feature 目录，含 8 个脚手架）；
- `.ai/tmp/p1683/baseline/historical_sha256.txt`：828 个历史 p157/p166/p167/p168 official 文件；
- `.ai/tmp/p1683/baseline/critical_sha256.txt`：4 个关键文件；
- `.ai/tmp/p1683/baseline/code_sha256.txt`：3 个工具文件；
- `.ai/tmp/p1683/baseline/protocol_sha256.txt`：3 个 Protocol/probe 文件。

---

## B. Eligibility Rule

### B.1 三个集合

| 集合 | 判定 | 当前数量 |
|---|---|---:|
| Registry Members | `Features/<id>/feature.yaml` 存在且可被 Registry 收录 | **31** |
| Scene Composer Eligible | Registry Member + `template.yaml` 存在 + `template.scene.source` 指向的入口场景真实存在 | **23** |
| Excluded / INCOMPLETE | Registry Member 但没有 `template.yaml`（因此未接入 Scene Composer） | **8** |

### B.2 实际实现

共享辅助函数放在 `test_scene_composer.py`：

```python
def scene_composer_eligible_ids(features_dir: str = FEATURES_DIR) -> list:
    eligible = []
    for fid in sorted(os.listdir(features_dir)):
        feature_dir = os.path.join(features_dir, fid)
        if not os.path.isdir(feature_dir):
            continue
        if not os.path.isfile(os.path.join(feature_dir, "feature.yaml")):
            continue
        template = template_loader.load_template(fid, features_dir)
        if not template:
            continue
        scene_rel = ((template.get("scene") or {}).get("source") or "").replace("\\", "/").strip()
        if not scene_rel or not os.path.isfile(os.path.join(feature_dir, scene_rel)):
            continue
        eligible.append(fid)
    return eligible
```

另外两个测试通过 `import test_scene_composer as eligibility` 复用同一函数，没有维护第二份排除名单。

### B.3 判定依据

- `FEATURE_SCHEMA.md` §7：`template.yaml` 可选；“无 template.yaml 的 Feature 视为未接入 Scene Composer”；
- `FEATURE_SCHEMA.md` §4：`capabilities.required` 可选，默认 `[]`；未声明的存量 Feature 继续合法；
- `template.scene.source` 是入口场景的直接声明；本规则要求它实际存在，避免把“有空模板但没有场景”的 Feature 算入；
- 没有硬编码 23；数量由当前数据推导。

### B.4 当前候选与排除

**23 个 Eligible：**

```text
attack_emitter, chase_movement, collect_pickup, condition_gate,
contact_damage, cooldown, heal_pickup, health, health_bar, hit_flash,
i_frames, knockback, moving_platform, openable_door, patrol_movement,
player_movement, projectile, save_game, screen_shake, sfx_pool,
state_machine, stun, trigger_switch
```

**8 个 Excluded（无 `template.yaml`）：**

```text
anima_behaviour, attribute_editor, audio_player_pool, blackboard,
clean_copy, flying_letter, pedestal_interaction, pickable_audio
```

排除原因均为同一个结构性事实：**没有 Scene Composer 模板**。它们仍保留在 Registry 中，只是不进入 Scene Composer / Capability / Adoption 的正式支持集。

---

## C. Changes

### C.1 `test_scene_composer.py`

- 新增 `scene_composer_eligible_ids()`，从 `feature.yaml + template.yaml + 实际入口场景` 派生候选；
- 原先遍历全部 31 个目录的模板检查改为遍历 Eligible 集合；
- 删除过时的“12 个 Feature”注释；
- 新增一个非硬编码的保护断言：至少存在一个 Eligible Feature，避免候选集意外为空导致空泛 PASS；
- 保留 `template: <id> exists` 和 `template: <id> source exists` 原有验证。

### C.2 `test_feature_capability_pipeline.py`

- 引入共享 `eligibility` 辅助；
- `real_features` 从“全部目录”改为 `scene_composer_eligible_ids()`；
- 更新 Phase 1.8.12 注释为 Phase 4 Eligibility 说明；
- 保留“读取器输出 == 自身 metadata 声明”和“Eligible Feature 已声明非空能力”的验证；
- 不改变 Capability 读取、去重、Gate 和 fixture 行为。

### C.3 `test_feature_capability_adoption.py`

- 引入共享 `eligibility` 辅助；
- `real_feature_ids()` 改为返回 Eligible 集合；
- 更新文档中的“12 个真实 Feature”旧规模表述；
- 保留正式 Feature 的“已登记能力 / 自身场景证据 / 单 Feature Intent / Gate / Contract / bare plan”全部审计断言；
- 不再对无场景入口的脚手架要求 `Node + 场景证据`。

### C.4 未修改

- 未修改任何生产代码；
- 未修改任何 `feature.yaml`、`template.yaml`、`.tscn`、`.gd`；
- 未修改 Registry、Schema、Contract、Evidence/Attestation；
- 未执行 Git add/commit/push/reset/clean。

---

## D. Test Results

### D.1 独立验证

每条命令单独启动 Python 进程：

| 测试 | PASS 行 | FAIL 行 | 耗时 | 退出码 | 结果 |
|---|---:|---:|---:|---:|---|
| `test_scene_composer.py` | 72 | 0 | 1s | 0 | **PASS** |
| `test_feature_capability_pipeline.py` | 37 | 0 | 2s | 0 | **PASS** |
| `test_feature_capability_adoption.py` | 230 | 0 | 3s | 0 | **PASS** |

### D.2 串行验证

在同一命令中按顺序启动三个独立进程：

| 测试 | PASS 行 | FAIL 行 | 耗时 | 退出码 | 结果 |
|---|---:|---:|---:|---:|---|
| `test_scene_composer.py` | 72 | 0 | 1s | 0 | **PASS** |
| `test_feature_capability_pipeline.py` | 37 | 0 | 1s | 0 | **PASS** |
| `test_feature_capability_adoption.py` | 230 | 0 | 4s | 0 | **PASS** |

日志目录：

```text
.ai/tmp/phase4_eligibility_logs_20261110/
```

包含：

- `test_scene_composer.log`
- `test_feature_capability_pipeline.log`
- `test_feature_capability_adoption.log`
- `serial_test_scene_composer.log`
- `serial_test_feature_capability_pipeline.log`
- `serial_test_feature_capability_adoption.log`

### D.3 候选集验证

使用共享辅助直接输出：

```text
eligible_count=23
excluded_count=8
```

`test_scene_composer` 日志中：

```text
template exists: 23 次
template source exists: 23 次
```

说明 23 个 Eligible Feature 全部进入了模板验证，且 8 个无模板脚手架全部未进入。

### D.4 未执行的测试

本阶段**没有**执行剩余 30 个全量测试，也没有执行 8 个脚手架的自测。未执行项不计为 PASS。

---

## E. Assertions Integrity

### E.1 静态断言数量

| 测试 | 修改前 `ok(` 数量 | 修改后 `ok(` 数量 | 说明 |
|---|---:|---:|---|
| `test_scene_composer.py` | 27 | 28 | 增加 1 个“候选集非空”保护断言；原有断言未删 |
| `test_feature_capability_pipeline.py` | 32 | 32 | 仅替换候选集合与注释 |
| `test_feature_capability_adoption.py` | 32 | 32 | 仅替换候选集合与注释 |

### E.2 未降低正式 Feature 验证

- `test_scene_composer.py`：仍验证每个 Eligible Feature 的模板存在、入口场景存在；没有删除断言。
- `test_feature_capability_pipeline.py`：23 个 Eligible Feature 仍全部要求非空能力声明，并逐项校验读取器输出与自身 metadata 一致；fixture 的 legacy 空能力测试保留。
- `test_feature_capability_adoption.py`：23 个 Eligible Feature 仍执行：
  - 能力只包含已登记能力；
  - 能力声明与自身场景/契约证据一致；
  - 单 Feature Intent 构建；
  - Gate PASS 并记录声明；
  - Contract PASS 及 bare plan 证据判定。
- 被排除的仅是 8 个没有 `template.yaml`、按 Schema 未接入 Scene Composer 的 INCOMPLETE 目录。

### E.3 没有通过删除断言取得 PASS

`git diff` 仅包含：

- 新增共享 Eligibility 函数；
- 候选集合替换；
- 过时注释更新；
- 1 个非空候选保护断言。

没有删除既有断言，没有跳过正式 Feature，没有修改生产逻辑。

---

## F. Feature Integrity

### F.1 全量 Feature 哈希核对

执行：

```text
sha256sum -c .ai/tmp/p1683/baseline/features_sha256.txt
```

结果：

```text
EXIT=0
OK=265
FAILED=0
```

该清单覆盖 `Features/` 下全部 265 个文件，包括：

- 23 个 Eligible Feature 的全部文件；
- 8 个 INCOMPLETE 脚手架的全部文件；
- `Features/FEATURE_SCHEMA.md`。

因此 23 个正式 Feature 和 8 个脚手架都未发生哈希变化。

### F.2 当前聚合哈希

| 集合 | 当前 SHA256 |
|---|---|
| 23 个 Eligible Feature 目录内容聚合 | `14ced960ba2121c44e3be10362a3ce2307a024926f55950fb8d32d6d0e9a691e` |
| 8 个 Excluded Feature 目录内容聚合 | `ae031a8011e59333a408af0abf92b2a99c22160919c7065283363c19e3adb6fe` |

聚合方式：按路径排序，对相对路径、NUL 和文件内容依次做 SHA256；不包含 `__pycache__`。

### F.3 Git 状态核对

- `git status --porcelain -- Features` 与基线相比没有新增修改；
- `find Features -newermt '2026-11-11 21:00:00'` 无输出，说明 Phase 4 期间没有 Feature 文件被写入；
- 8 个目录仍为未跟踪 `??`，没有被删除、移动、补模板或补能力。

---

## G. Repository Integrity

### G.1 Registry / Schema

| 检查 | 结果 |
|---|---|
| `feature_index.json` SHA256 与基线一致 | **PASS** |
| `feature_index.json` 仍保留 31 个 Registry Members | **PASS** |
| `feature_graph.json` SHA256 与基线一致 | **PASS** |
| `FEATURE_SCHEMA.md` SHA256 与基线一致 | **PASS** |

### G.2 Contract / Protocol / Code

执行 `sha256sum -c`：

| 清单 | 结果 |
|---|---|
| `critical_sha256.txt`（4 个关键文件） | 4 OK / 0 FAIL，exit 0 |
| `code_sha256.txt`（3 个工具文件） | 3 OK / 0 FAIL，exit 0 |
| `protocol_sha256.txt`（3 个 Protocol/probe 文件） | 3 OK / 0 FAIL，exit 0 |

### G.3 Evidence / Attestation

执行：

```text
sha256sum -c .ai/tmp/p1683/baseline/historical_sha256.txt
```

结果：

```text
EXIT=0
OK=828
FAILED=0
```

覆盖 p157/p166/p167/p168 的 official Evidence、Attestation、Bundle、Index、Run 文件。另确认：

```text
sha256(evidence_index.json) = 0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910
```

与历史报告记录一致。

### G.4 Dirty 范围

Phase 4 开始的 dirty 为 1056；当前为 1059（Phase 4 报告生成前）。差异仅：

```text
 M .ai/tools/scene_composer/tests/test_feature_capability_adoption.py
 M .ai/tools/scene_composer/tests/test_feature_capability_pipeline.py
 M .ai/tools/scene_composer/tests/test_scene_composer.py
```

Phase 4 报告本身生成后，dirty 将为 1060。与 Phase 1 快照的差异还包括此前阶段已生成的 3 份报告：

```text
?? .ai/context/PHASE_1_68_3_1_PHASE_2_ROOT_CAUSE_REPORT.md
?? .ai/context/PHASE_1_68_3_1_PHASE_3_1_FEATURE_ELIGIBILITY_AUDIT.md
?? .ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md
```

没有覆盖或清理 Phase 1 的 1053 项 dirty 内容；没有未授权的额外源码修改。

---

## H. Final Verdict

**PASS**

理由：

1. 三个目标测试独立执行全部 PASS，退出码均为 0；
2. 三个目标测试串行执行全部 PASS，退出码均为 0；
3. 23 个 Eligible Feature 全部进入候选集合；
4. 8 个 INCOMPLETE 脚手架全部被排除；
5. Registry 仍保留 31 个成员；
6. 正式 Feature 的验证断言没有降低，未删除断言或跳过正式 Feature；
7. 265 个 Feature 文件哈希全部 OK（0 FAILED）；
8. 828 个历史 Evidence/Attestation 文件哈希全部 OK（0 FAILED）；
9. Registry、Schema、Contract/Protocol 和 evidence_index 哈希均未变化；
10. 未修改生产代码或 Feature 数据，未执行 Git 写操作，未执行剩余 30 个测试。

Phase 4 完成。等待用户审查本报告后再进入 Phase 5 Regression。
