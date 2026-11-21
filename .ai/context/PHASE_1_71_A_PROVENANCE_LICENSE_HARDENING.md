# Phase 1.71 — Batch A: Provenance & License Hardening

**Status:** PASS  
**Date:** 2026-11-13  
**Scope:** Controlled implementation, Batch A only  
**Batch B:** NOT STARTED (waits for user acceptance of this report)

---

## A. Executive Summary

Batch A 已完成，核心目标是让外部代码在进入 Catalog、Reference、Promote 或后续复制流程之前，具有明确的来源与许可证判定。

实现结果：

- 新采集数据使用完整 40 位 Commit SHA；
- 新 Source URL 固定到 Commit，不再使用分支名；
- `commit_sha` 保留 12 位以兼容旧数据，同时新增 `commit_sha_full`；
- Fetch、Catalog、Promote 共用同一 License Gate；
- `--repo` 与 `--all` 不再绕过许可证限制；
- 历史短 SHA 标记为 `incomplete`，没有伪造完整 SHA；
- 新增只读 Provenance Validator；
- 新增 38 项 Batch A 隔离测试；
- 原有 Phase 1.69 Collector/Search 回归测试 41 项全部通过；
- 没有重建 Catalog/INDEX，没有修改 Source/Reference Library。

**Batch A verdict:** `PASS`

---

## B. Architecture Changes

### B.1 Modified existing component

#### `.ai/skills/foundation/godot-gdscript/tools/github_collector.py`

职责保持不变：Search / Fetch / Catalog / Check / Reindex / Backfill / Promote。

Batch A 增加：

1. **Fetch 前完整 SHA 解析**
   - 通过 GitHub commits API 获取 40 位 SHA；
   - 无法取得完整 SHA 时失败，不退回分支名；
   - `_meta.json` 同时保存：
     - `commit_sha`（12 位，兼容旧消费者）
     - `commit_sha_full`（40 位）
     - `provenance_status`

2. **Fetch 原子安装**
   - 下载和抽取写入同级 staging 目录；
   - 校验并写入完整 `_meta.json` 后才替换目标目录；
   - 已存在的目标在 `--force` 下使用备份替换；
   - 失败不会留下半成品 Source。

3. **许可证检测**
   - Fetch 后检查根级 `LICENSE*` / `COPYING*`；
   - 记录 `license_text_present`、`license_files`、`license_status`；
   - 根级文本缺失时记录 `license_text_missing`，不伪造“已取得许可证文本”。

4. **Fetch License Gate**
   - `--repo`、`--all`、普通 candidates 均先经过 `assess_license()`；
   - `blocked` / `unknown` / `pending_review` 不复制；
   - 被阻止的 Repository 会返回明确错误；
   - `--all` 表示“发现全部候选”，不再表示“绕过许可证”。

5. **Catalog License/Provenance Gate**
   - `_preflight_sources()` 在写临时目录前检查许可证与来源；
   - 非白名单或来源未知时 Catalog 失败；
   - 保留原有 stage / validate / backup / rollback。

6. **Catalog 新字段**
   - `commit_sha_full`
   - `source_url` 使用完整 SHA；历史短 SHA 使用短 SHA，不使用分支
   - `provenance_status`
   - `license_text_present`
   - `license_status`
   - `license_source`
   - `license_basis`

7. **Promote License/Provenance Gate**
   - 在创建 `Features/<name>/` 之前检查；
   - 非白名单、未知许可证阻止；
   - 来源未知阻止；
   - 短 SHA 只警告 `incomplete`；
   - 本地许可证文本缺失时警告并记录既有策略依据；
   - 被阻止时不会留下 Feature 半成品。

8. **Backfill 兼容**
   - 回填完整 SHA 时同步 `commit_sha_full`、`source_url`、`provenance_status`；
   - 不自动猜测缺失 SHA；
   - 未执行 Backfill。

### B.2 New components

#### `.ai/tools/external_code/provenance.py`

共享、无副作用的来源与许可证判定模块。

职责：

- SPDX 白名单判定；
- `eligible / pending_review / blocked / unknown / license_text_missing` 状态；
- 完整/短/缺失 SHA 判定；
- 不可变 Source URL 生成；
- 根级许可证文本检测；
- Fetch 元数据 enrichment。

#### `.ai/tools/external_code/provenance_validator.py`

只读验证入口，支持：

- `--repo`：单个 Source Repository；
- `--reference`：单个 Reference；
- `--entry`：单个 Catalog Entry；
- `--catalog`：Catalog（可选路径）；
- `--json`；
- `--limit`。

输出状态：

- `valid`
- `incomplete`
- `invalid`

退出码：

- `0` valid
- `1` incomplete
- `2` invalid

检查内容：

- Repository 身份、URL、路径；
- Commit SHA 完整性；
- Source URL 是否固定到 Commit；
- License metadata 与本地文本；
- Catalog/Source/Reference 一致性；
- Source SHA256；
- Duplicate 目标；
- 空 Reference。

#### `.ai/tools/external_code/tests/test_batch_a.py`

Batch A 隔离测试，全部写入临时目录。

#### `.ai/context/PHASE_1_71_PREFLIGHT.md`

Preflight 基线报告。

---

## C. Provenance Schema

### C.1 Source `_meta.json` 新字段

| Field | Meaning |
|---|---|
| `commit_sha` | 12 位短 SHA，兼容旧消费者 |
| `commit_sha_full` | 40 位完整 SHA |
| `provenance_status` | `complete` / `incomplete` / `unknown` |
| `license_source` | 例如 `github_api_spdx` |
| `license_text_present` | 根级 LICENSE/COPYING 是否存在 |
| `license_files` | 检测到的根级许可证文件名 |
| `license_status` | `eligible` / `pending_review` / `blocked` / `unknown` / `license_text_missing` |
| `license_basis` | 判定依据 |
| `license_risk` | 例如 `local_license_text_missing` |
| `copy_allowed` | 该元数据是否允许复制 |

### C.2 Catalog 新字段

Catalog 保持旧字段兼容，新增：

- `commit_sha_full`
- `provenance_status`
- `license_text_present`
- `license_status`
- `license_source`
- `license_basis`

### C.3 兼容策略

- 旧 Catalog 没有新字段仍可被读取。
- 旧 `commit_sha` 12 位保持有效，但 `provenance_status` 为 `incomplete`。
- 不为旧数据生成未经 API 验证的 40 位 SHA。
- 不修改现有 Catalog；新字段将在下一次明确授权的 Catalog 生成后出现。
- 旧 Source URL 的分支形式不会被自动改写；Validator 会标记为不完整。
- `source_url` 对新数据使用：
  `https://github.com/{owner}/{repo}/blob/{40-sha}/{source_path}`

---

## D. License Gate

### D.1 状态决策

| Condition | Status | Copy Allowed |
|---|---|---|
| 白名单 SPDX + 本地许可证文本 | `eligible` | 是 |
| 白名单 SPDX，无本地文本 | `license_text_missing` | 是，按既有 SPDX 白名单策略；记录风险 |
| 非白名单 | `blocked` | 否 |
| 缺失/UNKNOWN/NOASSERTION | `unknown` | 否 |
| 明确标记待审 | `pending_review` | 否 |

### D.2 入口覆盖

- `fetch --repo`：受 Gate 约束；
- `fetch --all`：受 Gate 约束；
- 普通 `fetch --top`：受 Gate 约束；
- `catalog`：受 Gate 约束；
- `promote`：受 Gate 约束；
- `search`：不受复制 Gate 阻断，仍可查看待审/阻止记录。

### D.3 四个已知缺本地许可证文本的仓库

仍保持缺失标记，不推断已补齐：

- `anthonyec__godot_little_camera_preview`
- `fenix-hub__godot-engine.easy-charts`
- `nathanhoad__godot_sound_manager`
- `Portponky__better-terrain`

由于它们使用白名单 SPDX 标识，按现有项目策略可复制，但状态为 `license_text_missing`，风险为 `local_license_text_missing`。

---

## E. Tests

### E.1 Batch A test suite

命令：

```bash
python .ai/tools/external_code/tests/test_batch_a.py
```

结果：**38 / 38 PASS**

覆盖：

| Area | Checks |
|---|---:|
| License: MIT / Unlicense / GPL / unknown / empty / missing local text | 6 |
| Provenance: full / short / missing SHA | 3 |
| Catalog: full SHA, immutable URL, short SHA, missing license text | 8 |
| Fetch: local in-memory tarball, full SHA, license detection | 3 |
| Catalog: GPL blocked, old data preserved | 2 |
| Fetch: `--all` and `--repo` cannot bypass | 2 |
| Promote: blocked, no half-created Feature | 2 |
| Search: pending/blocked records discoverable | 1 |
| Provenance validator: valid / incomplete / invalid cases | 8 |
| Validator fixture / repository check | 3 |

实际输出结尾：

```text
PASS: Batch A 38 checks
```

### E.2 Existing regression

命令：

```bash
python .ai/tools/feature_registry/tests/test_phase169_tooling.py
```

结果：**41 / 41 PASS**

覆盖：

- Collector preflight 失败保护；
- Catalog 生成与 SHA 去重；
- Catalog 写入失败回滚；
- 替换失败回滚；
- Search Catalog 缺失/空/非法；
- Search 去重、`--all`、JSON、CLI。

### E.3 Syntax check

```bash
python -m py_compile ...
```

通过。

### E.4 Validator smoke check

对真实 `ceceppa__anima` Source 执行只读检查：

- 结果：`incomplete`
- 原因：只有 12 位历史短 SHA，未伪造完整 SHA
- License：`eligible`
- Provenance：`incomplete`

这是预期结果，不是失败。

### E.5 Not covered in Batch A

- 未执行真实 GitHub 网络下载；Fetch 使用本地内存 tarball 覆盖 staging 流程。
- 未对全部 77 个历史 Repository 执行 Validator。
- 未执行全量 Catalog 重建。
- 未执行 Batch B 的 Parser/Adapter 测试。

---

## F. Data Safety

- Source Library：未修改。
- Reference Library：未修改。
- `catalog.yaml`：未重建。
- `INDEX.md`：未重建。
- `Features/`：未修改。
- `knowledge_v2` / approved knowledge：未修改。
- 所有 Batch A 测试使用系统临时目录。
- `git status -- .ai/skills/foundation/godot-gdscript/code_library`：0 行。
- 未执行任何 Git 写操作。

---

## G. Git & Workspace

### G.1 Phase 1.71 本次新增/修改

修改：

- `.ai/skills/foundation/godot-gdscript/tools/github_collector.py`

新增：

- `.ai/tools/external_code/provenance.py`
- `.ai/tools/external_code/provenance_validator.py`
- `.ai/tools/external_code/tests/test_batch_a.py`
- `.ai/context/PHASE_1_71_PREFLIGHT.md`
- `.ai/context/PHASE_1_71_A_PROVENANCE_LICENSE_HARDENING.md`

### G.2 原有工作区

Preflight 已记录：

- HEAD：`d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84`
- origin/master：同 HEAD
- ahead/behind：`0 / 0`
- staged：0
- modified：26（Preflight 时）
- untracked：138（Preflight 时）
- conflicts：0
- 远端实际状态：UNKNOWN（未 Fetch）

Batch A 后：

- staged：0
- modified：27（原有 26 + Collector）
- untracked：143（原有 138 + Preflight、3 个 external_code 文件、Batch A 报告）
- Code Library 变更：0
- 未执行 `git add/commit/push/fetch/pull/checkout/reset/clean/stash/rebase/merge`

原有 26 个 modified 文件没有被本 Phase 修改或归因。

---

## H. Residual Risks

1. **`license_text_missing` 仍可复制**
   - 这是沿用项目既有 SPDX 白名单策略；
   - 已记录 `license_basis` 与 `license_risk`；
   - 如需更严格政策，应单独决定是否将本地文本设为硬性要求。

2. **历史数据仍是短 SHA**
   - 没有自动回填；
   - Validator 会报告 `incomplete`；
   - 需要单独授权的 Backfill 才能补齐。

3. **历史 Source URL 可能仍是分支 URL**
   - 未重建 Catalog/Reference；
   - 新数据已固定到 Commit；
   - 旧数据由 Validator 标记。

4. **真实网络 Fetch 未在 Batch A 中执行**
   - 本地 tarball 已覆盖 staging、SHA 元数据、许可证检测；
   - GitHub API 的真实网络行为未在本阶段验证。

5. **`provenance_validator` 默认全量会返回 `incomplete`**
   - 因为历史 Catalog 全部是 12 位 SHA；
   - 这是如实报告，不是系统错误。

---

## I. Batch A Acceptance

- [x] 来源信息结构明确。
- [x] 新数据能够保存完整 Commit SHA。
- [x] 新数据 Source URL 固定到不可变 Commit。
- [x] License Gate 覆盖 Fetch、Catalog、Promote。
- [x] `--repo` 无法绕过。
- [x] `--all` 无法绕过复制限制。
- [x] 未确认许可证不能进入代码资产目录。
- [x] 被阻止的 Promote 不产生半成品。
- [x] Provenance Validator 可用且只读。
- [x] 历史不完整数据不会被伪造补全。
- [x] Batch A 隔离测试 38/38 通过。
- [x] 原有 Collector/Search 回归 41/41 通过。
- [x] Source/Reference/Catalog/INDEX/Features 未被修改。
- [x] 未执行 Git 写操作。

---

## J. Final Verdict

# `PASS`

Batch A 的实现与测试已完成。  
Batch B 尚未开始，按任务书要求等待用户验收本报告后再继续。
