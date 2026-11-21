# PHASE 1.78
## Parser Identity Contract & Write Protection Design

**Task Type:** IDENTITY CONTRACT & WRITE PROTECTION ARCHITECTURE DESIGN
**Phase:** 1.78
**Execution Mode:** STRICT READ-ONLY AUDIT + IMPLEMENTATION DESIGN
**Implementation:** PROHIBITED（未修改任何工具、Schema、字段）
**Formal Data Mutation:** PROHIBITED（8 个受保护清单 8/8 与本阶段开始前一致）
**Reanalysis:** PROHIBITED（未重跑 34 条，未重跑 Batch B）
**Git Mutation:** PROHIBITED（未 stage / commit / push / reset / checkout / clean）
**前置:** Phase 1.77 = `PASS_WITH_LIMITATIONS` / `READY_FOR_IDENTITY_IMPLEMENTATION_DESIGN`

标注约定（全文强制）：

- `EVIDENCE_CONFIRMED` — 由本阶段真实源码或真实数据实测得出。
- `DESIGN_RECOMMENDATION` — 设计建议，**尚未实现**，不得当作现有能力。
- `OPEN_QUESTION` — 需人工决策，本阶段不自行裁定。
- `NOT_VERIFIED` — 本阶段未验证（含因禁止实施而无法验证）。

---

## A. Executive Summary

本阶段的目标不是"再审计一次"，而是产出一份**可以直接指导下一阶段实施**的身份契约 + 写入保护设计。

### A.1 三条核心结论

| # | 结论 | 标注 |
|---|---|---|
| 1 | Analysis ID 当前是**输入身份 + 声明版本号**的函数，既不含实际执行的 Parser 实现，也不含输出内容；同版本内实现变化对身份不可见（Batch E 已真实发生） | `EVIDENCE_CONFIRMED` |
| 2 | 现有下游把身份**同时当作主键、文件名和字节摘要锚点**：150 条 Linkage 内嵌 `analysis_record_digest`（Analysis 文件原始字节 sha256），Candidate 再内嵌 Linkage 摘要。因此"就地给 34 条记录补字段"会立即让 150 条 Linkage 全部 STALE/INVALID | `EVIDENCE_CONFIRMED` |
| 3 | `write_record` 无存在性守卫，同名即覆盖（已在隔离临时目录实证：1 个路径、内容被覆盖、无 `record_id`）；但 `write_linkage` 已经实现"临时文件 + 校验 + `os.replace`"的原子写范式，可作为写入守卫的直接参照 | `EVIDENCE_CONFIRMED` |

### A.2 本阶段新增发现（Phase 1.77 未记录，均实测）

| # | 发现 | 证据 |
|---|---|---|
| N-1 | 34 条正式 Analysis 文件全部为 **CRLF** 行尾，150 条 Linkage 全部为 **LF** 行尾 | 逐字节扫描：34/34 CRLF；150/150 LF |
| N-2 | 34 条记录的内容可用 `json.dumps(sort_keys, indent=2) + "\n"` 经 CRLF 转换后 **34/34 字节复现**；用 LF 则 **0/34** | 复算实验 |
| N-3 | 因此 `analysis_record_digest`（raw bytes sha256）**依赖操作系统行尾**：同一逻辑记录在 LF 环境下摘要必然不同 → 跨平台校验必失败 | `write_record` 用 `Path.write_text`（文本模式，Windows 换行转换）；`write_linkage` 显式 `newline="\n"` |
| N-4 | `test_batch_b.py:127-128` 断言同一记录二次写入"幂等"（`path1 == path2`） | 若守卫一律拒绝覆盖，该既有测试会失败 → 守卫必须允许 `REUSE_IDENTICAL` |
| N-5 | `analysis_id` 同时被当**文件名**消费（`evidence_impact_176.py:757`、`manual_evidence_review_176.py:654-655`） | 改 ID 即改路径 |
| N-6 | Parser 依赖闭包含 `.ai/tools/learning/paths.py`（`source_analysis.py:26`），当前 Build Identity 只哈希 2 个文件，**未覆盖该依赖** | `sha256(paths.py)=c6f5f12e…` |
| N-7 | 闭包内 5 个模块均**不读环境变量**（无 `getenv`/`environ`） | 逐文件扫描 |
| N-8 | 34 条记录的 5 元组（repo, commit_full, source_path, input_digest, source_digest）**34/34 唯一**，无重复身份 | 分组统计 |
| N-9 | 现有 34 条记录的 canonical 输出摘要 **34/34 互不相同**，因此"输出冲突"场景**今天无法在正式数据上取到真实样本**，只能合成测试 | 内存 canonical digest |
| N-10 | 4 个文件处于 ` M` 但 `git diff` 无内容差异（stat-only）：`Features/{knockback,save_game,sfx_pool,state_machine}/feature.yaml` | Git 实测 |

### A.3 判定

| 项 | 值 |
|---|---|
| **Verdict** | **`PASS_WITH_LIMITATIONS`** |
| **Readiness** | **`READY_FOR_IDENTITY_IMPLEMENTATION`** |
| 限制 | ①全部字段与守卫均为设计，未落地（`NOT_VERIFIED`：落地后行为）；②守卫的"授权替换"契约只有设计，无实现；③跨平台摘要修复需要新写入口径，历史 150 条摘要不可能回溯重算为 LF 摘要（只能登记双摘要）；④Range/语义层不在本阶段范围 |

`READY_FOR_IDENTITY_IMPLEMENTATION` 仅表示**契约足以指导实施**，**不构成实施授权**。

---

## B. Baseline & Git Integrity

### B.1 真实 Git 状态（`EVIDENCE_CONFIRMED`）

| 项 | 实测值 |
|---|---|
| Project Root | `F:/Godot_v4.7-stable/game`（`/f/Godot_v4.7-stable/game`） |
| Branch | `master` |
| HEAD | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged | **0** |
| Deleted | **0** |
| `git status --porcelain` 行数 | **180** = `35` 条 ` M` + `145` 条 `??` |
| `git diff --name-only`（真实内容差异） | **31** |
| stat-only 修改（仅 stat 脏，无内容差异） | **4**：`Features/knockback/feature.yaml`、`Features/save_game/feature.yaml`、`Features/sfx_pool/feature.yaml`、`Features/state_machine/feature.yaml` |
| 未跟踪文件（展开） | **593** |
| 本阶段新增/修改的已跟踪文件 | **0** |
| 本阶段新增文件 | **1**：本报告（`.ai/context/` 下，属未跟踪目录内新增） |
| 本阶段临时文件 | 3 个（`.ai/tmp/phase178_probe{,2,3}.py`，阶段结束删除） |

### B.2 与 Phase 1.77 报告口径的差异（必须显式说明，不得掩盖）

Phase 1.77 的 T 节写作 `Modified 31 / Untracked 145 行 / 593 文件`，而 porcelain 实际为 180 行。

| 口径 | 数值 | 含义 |
|---|---|---|
| `git status --porcelain` 总行数 | 180 | 全部工作区条目 |
| 其中 ` M` | 35 | 索引与工作区 stat 不同（含 4 个 stat-only） |
| 其中 `??` | 145 | 折叠后的未跟踪条目（展开 593 文件） |
| `git diff --name-only` | 31 | **真实内容差异**的已跟踪文件 |

结论修正：Phase 1.77 报告的"145 行"是**只数了 `??` 行**的不完整口径（31 + 145 = 176 ≠ 180，漏掉 4 条 stat-only ` M`）。该差异**不影响** Phase 1.77 的两项关键声明：

- 本阶段/上一阶段未执行任何 Git 写操作 → `HEAD` 仍为 `d64b1cd5…`，staged 0、deleted 0，**成立**；
- 受保护文件 0 修改 → 8 个清单 SHA-256 8/8 一致，**成立**（见 S 节）。

本阶段不复述、不修改 Phase 1.77 报告；差异记录于此，供人工验收。

### B.3 受保护数据清单（Batch E 同一方案，`EVIDENCE_CONFIRMED`）

方案（与 Batch E 完全一致，可逐位比对）：递归遍历目标目录 → 仅取 `.json/.md/.yaml/.yml/.gd` → 按路径排序 → 对每个文件依次 `update(相对路径的 posix 形式)` 与 `update(文件字节 sha256 的十六进制字符串)` → 汇总 sha256。

| 路径 | 文件数 | SHA-256 |
|---|---|---|
| `.ai/learning/external_code/analysis` | 34 | `8202f322fe5cb166f3a2aaaf15617f53a708077a6794a8dc6a60be33e16b9a0c` |
| `.ai/learning/external_code/feature_links` | 150 | `ce7edc060a5d7917712d8ea0292069d4019c95a9bb52b3e48c935724faa48cd4` |
| `.ai/learning/external_code/reanalysis` | 191 | `53859cb96641bfae9ef146bae262a048b391d28ee0af30be656450e0e666da9c` |
| `.ai/learning/external_code/reconciliation` | 1 | `66ba91f05f00325b74d71f2029ee80210c661101d56cfd433e4d2d205d9dfb62` |
| `.ai/learning/external_code/evidence_impact` | 8 | `c1abd1ba2150818abe3b60732ab0695de316a759a46e8b80f5d351c2a8386695` |
| `.ai/learning/external_code/evidence_review` | 6 | `0220a4840cd1224a957a87d9a419c0856ba05eb081cf485c966a248423730be6` |
| `.ai/learning/candidate_workspace` | 3 | `b991d4f547266ea60980f1cf781ae735c5a8e9014699aa79662fca4c19f4491d` |
| `code_library`（sources + references） | 13 807 | `87af1d7f1ba7abce6cf127d28bc1ed2a35bdd3debc78880c1c5ab09a560606f5` |

与 Batch E / Phase 1.77 **8/8 IDENTICAL**。阶段内受保护文件写入 **0**。

---

## C. Phase 1.77 Findings Verification（独立复核，不复制结论）

全部以本阶段自己的脚本重算，**未引用** 1.77 报告的中间产物。

| # | Phase 1.77 结论 | 本阶段复核方法 | 结果 | 标注 |
|---|---|---|---|---|
| C-1 | `PARSER_VERSION` 参与 Analysis ID | 读 `external_code_understanding.py:52-54` | 成立：`sha256(repo|commit|path|input_digest|"gd_parse"|PARSER_VERSION)[:16]` | `EVIDENCE_CONFIRMED` |
| C-2 | 34 条 ID 在 1.71 下 34/34、1.75 下 0/34 | 内存复算（不写盘） | **1.71: 34/34；1.75: 0/34；1.76: 0/34** | `EVIDENCE_CONFIRMED` |
| C-3 | 34 条均为 `parser_version=1.71` | 逐条读取 | 34/34 = `1.71` | `EVIDENCE_CONFIRMED` |
| C-4 | 34 条无 `parser_build_identity` | 字段存在性统计 | 0/34 存在；**同时** `parse_execution_status`/`syntax_coverage_status`/`analysis_completeness`/`unsupported_constructs`/`unrecognized_declarations`/`source_coordinates` 全部 **0/34** | `EVIDENCE_CONFIRMED` |
| C-5 | Build Identity 只在 Batch B manifest | 读 `parser_1.76/manifest.json` | 顶层 `parser_build_identity` = `gd_parse@1.75+build:6b74a6cd20a06033`，含 12 个键（`gd_parse_sha256`/`adapter_sha256`/`identity_sha256`/…）；29 条重分析记录自身无该字段 | `EVIDENCE_CONFIRMED` |
| C-6 | 同版本不同实现可产生相同 ID、不同输出（Batch E） | 逻辑推演 + 1.75 复算 | 成立：ID 只取 `PARSER_VERSION` 字符串，实现替换不改变 ID；Batch E 已实证输出改变。**但"34 条上采集到同 ID 不同输出"今天不存在**（C-9 唯一性） | `EVIDENCE_CONFIRMED`（机制）/ `NOT_VERIFIED`（正式数据样本） |
| C-7 | `write_record` 无守卫直接覆盖 | 源码 + 隔离临时目录模拟 | 成立：同一 `analysis_id` 两次写入 → 同一路径、内容被覆盖、目录内 1 个文件 | `EVIDENCE_CONFIRMED` |
| C-8 | 150 条 Linkage 依赖 Analysis ID | 复算 `linkage_id`，检查外键 | `linkage_id` 150/150 复算一致；`analysis_id` 引用 150/150 均存在，**悬挂 0** | `EVIDENCE_CONFIRMED` |
| C-9 | 下游假设同 ID = 同输出 | canonical 输出摘要分组 | 34 条输出摘要 **34/34 唯一**，无并列 → 现有数据未暴露冲突 | `EVIDENCE_CONFIRMED` |
| C-10 | `source_digest` 不参与 ID | 读 `_analysis_id` 签名 + 复算 | 成立（签名 4 个内容字段中不含 `source_digest`） | `EVIDENCE_CONFIRMED` |
| C-11 | Seed Policy 无 Parser 门禁 | 读 `candidate_seed_policy.json` + `evidence_impact_176.py:808-830` | 成立：`policy_version=phase-1.74-c/1`，3 seeds + 1 context relation，均以 `linkage_id` 为键；无 `parser_version`/`build`/`coverage` 门禁字段 | `EVIDENCE_CONFIRMED` |

### C.1 本阶段新增的契约级事实（决定设计约束）

| # | 事实 | 影响 |
|---|---|---|
| C-12 | Linkage 记录含 `external_analysis.analysis_record_digest`，且 `verify_record_sources()` 在**写入与校验**时强制比对当前文件字节；`evaluate_freshness()` 不一致即判 `STALE` | 34 条 Analysis **任何字节改动**都会让 150 条 Linkage 变成 STALE/INVALID。禁止"就地补字段" |
| C-13 | 34 条 Analysis 为 CRLF，150 条 Linkage 为 LF；`analysis_record_digest` 是 raw bytes 摘要 | 摘要跨平台不可复现；身份契约必须改为"canonical 内容摘要 + 可选原始字节摘要"双轨 |
| C-14 | Candidate Eligibility 从 Linkage 取 `analysis_id` + `analysis_record_digest` + `linkage_record_digest` | Candidate 层同样钉住字节，迁移必须通过新结果而非改旧文件 |
| C-15 | `write_linkage()` 已经是"validate → 临时文件 → 重新读取校验 → `os.replace`"的原子写 | 写入守卫有可复用的本地范式（设计参照，不复制实现） |
| C-16 | Build Identity 只哈希 2 个文件，未覆盖 `paths.py` | 依赖闭包定义不完整（N-6） |
| C-17 | Parser 闭包不读环境变量 | 运行时指纹可只记录解释器/平台，不必登记 env |

---

## D. Stage B — Identity Domain Model

原则：**一个哈希不能承载全部语义**。本阶段把身份拆成 8 层，并明确"谁参与哈希、谁只做 provenance"。

### D.1 Source Identity（源对象身份）

候选字段：`source_repository` / `source_commit` / `source_path` / `source_digest`

| 项 | 设计规则 | 标注 |
|---|---|---|
| Repository 规范化 | 保留 GitHub `owner/repo` 原样大小写；不做 `casefold`（大小写不同视为不同 repo）；拒绝 git URL、`.git` 后缀、尾部 `/` | `DESIGN_RECOMMENDATION` |
| Commit | 40 位小写十六进制为**唯一可信形态**；短 SHA 允许存在但必须同时带 `source_commit_status=LEGACY_SHORT`，不得作为内容相等依据 | `DESIGN_RECOMMENDATION` |
| Source Path | repo 相对路径、POSIX 分隔符、无前导 `./`、不做大小写折叠（区分大小写的仓库确实存在）；子模块路径按"外层 repo + 子模块路径"整体记录，不展开 | `DESIGN_RECOMMENDATION` |
| Source Digest | `sha256(pinned source 文件原始字节)`；编码不做转码；换行**不归一化**（源文件字节即事实） | `DESIGN_RECOMMENDATION` |
| 符号链接 | 若 pinned source 是符号链接：记录 `source_symlink=true` 与目标路径，digest 取目标内容，不解析跨仓库链接 | `DESIGN_RECOMMENDATION` |
| 缺失文件 | `source_digest=""` + `source_status=MISSING`，**不得**用空串参与哈希（见 D.6） | `DESIGN_RECOMMENDATION` |

**关键判断（`EVIDENCE_CONFIRMED`）：** 相同 `repo + commit + path` **不足以**保证源码内容一致。理由：①当前工作区存在未提交修改与未跟踪文件（本阶段实测 31 内容差异 + 593 未跟踪）；②pinned source 副本可能被本地改动而不改 commit；③`source_digest` 今天已在 34 条记录中独立存在（34/34 有值）。故 `source_digest` 是**必需**的独立字段，不可省略。

### D.2 Input Identity（实际被分析的输入身份）

候选字段：`input_digest` / `input_source_type` / `input_reference_offset` / `input_normalization_version`

| 项 | 设计规则 | 标注 |
|---|---|---|
| 实际分析输入 | **Reference 副本**（`reference_path`），不是 pinned source。证据：`analyze_external_code()` 读取 `path`（Reference）字节算 `input_digest`，`parse_text(str(path), text)` 解析的是 Reference 文本 | `EVIDENCE_CONFIRMED` |
| `input_digest` | `sha256(Reference 原始字节)`，34/34 与当前文件字节一致 | `EVIDENCE_CONFIRMED` |
| Source vs Reference 差异 | 由 `input_reference_offset`（Reference 相对 pinned source 的前导行数）+ `source_consistent` 表达；当前 34 条各自记录 `reference_offset` 与 `source_consistent` | `EVIDENCE_CONFIRMED`（字段存在）/ `DESIGN_RECOMMENDATION`（进入身份契约） |
| Reference Header | 属于 Input 身份的一部分（改变 header → 改变 `input_digest` → 改变分析输入），但**不属于** Source 身份 | `DESIGN_RECOMMENDATION` |
| 规范化版本 | `input_normalization_version="bytes-v1"`：当前"不归一化，直接用原始字节"的语义显式化；将来若引入换行归一化必须换版本号 | `DESIGN_RECOMMENDATION` |
| 可独立复算 | 是：任意第三方可用 Reference 文件字节重算 `input_digest` | `EVIDENCE_CONFIRMED` |
| 映射失败 | `input_reference_offset=null` + `source_consistent=false` + `input_mapping_status=UNALIGNED`；此时**允许**分析继续，但禁止把行号提升为 commit 行号 | `DESIGN_RECOMMENDATION` |

**不得合并**：`source_digest`（pin 的仓库内容）与 `input_digest`（实际喂给 Parser 的副本字节）语义不同。当前 `_analysis_id` 只含后者，正是"来源变了但 Reference 没变"无法被识别的原因（`EVIDENCE_CONFIRMED`：`_analysis_id` 签名不含 `source_digest`）。

### D.3 Parser Identity（三层，必须分开）

| 字段 | 含义 | 规则 | 标注 |
|---|---|---|---|
| `parser_version` | **声明协议版本**（当前 `"1.75"`） | 语义类变化必须递增；允许历史记录停留在旧版本且**不追溯改写**；**不参与**内容身份；参与 Reanalysis 判断 | `DESIGN_RECOMMENDATION` |
| `parser_build_identity` | **实际执行的实现身份** | 由运行时从源码字节确定性计算，见 F 节；**必须**写入每条新记录；无法确定时写 `UNKNOWN`，不得猜测 | `DESIGN_RECOMMENDATION` |
| `parser_contract_version` | **输出契约版本**（Symbol/Unsupported/Coverage/Location/字段语义） | 与实现解耦：仅当"输出结构或字段语义"变化时递增；不随每次代码修改递增 | `DESIGN_RECOMMENDATION` |

**为什么实现与契约必须分开（`EVIDENCE_CONFIRMED` 依据 Batch E）：** Batch E 改变了实现（声明形态识别、coverage 判定），使输出从"报 COMPLETE"变为"报 PARTIAL"，这既改了实现也改了**输出语义**；而 1.75 中存在的"纯重构、输出字节不变"改动只改实现。二者必须能被区分，否则"实现变了但输出没变"会被迫触发全量重分析。

### D.4 Adapter Identity

| 字段 | 含义 | 规则 | 标注 |
|---|---|---|---|
| `adapter_version` | Adapter 声明版本（当前**不存在**，仅有文件名） | 新增常量 | `DESIGN_RECOMMENDATION` |
| `adapter_build_identity` | `sha256(adapter.py 字节 || 0x00 || 其直接依赖字节)` | 与 Parser Builder 同法但独立计算 | `DESIGN_RECOMMENDATION` |
| `adapter_contract_version` | 记录结构/字段投影契约版本 | 仅结构/语义变化时递增 | `DESIGN_RECOMMENDATION` |

职责归属（`EVIDENCE_CONFIRMED`，全部在 `external_code_understanding.py`）：

- Parser（`gd_parse.py`）只产出 `Script` 与 `coverage`；
- **Adapter 负责**：`_analysis_id`、`input_digest`/`source_digest`、`_reference_offset`、`_coverage_with_coordinates` 的行号投影（`source_line`/`record_line`）、`analysis_status` 分类、记录序列化；
- 因此 **Reference Offset 与三类行号投影属于 Adapter 行为**，不属于 Parser。

Adapter 变化的处理（`DESIGN_RECOMMENDATION`）：Adapter 变**不得**自动触发 Parser 重分析；若 Parser 输出未变而 Adapter 输出结构变化 → `RECORD_MIGRATION`；若 Adapter 变化改变了 Symbol 选取/状态分类 → `REVALIDATE`（必要时 `REANALYZE`）。

### D.5 Analysis Schema Identity

| 字段 | 含义 | 规则 | 标注 |
|---|---|---|---|
| `analysis_schema_version` | 现有 `SCHEMA_VERSION=1` | 仅**不兼容结构变化**递增；新增可选字段不递增 | `DESIGN_RECOMMENDATION` |
| `analysis_schema_identity` | Schema 契约摘要（字段名/类型/必填/枚举的规范化摘要） | 与版本号并存：版本号便于人读，摘要便于机器验证"版本号没变但 Schema 悄悄变了" | `DESIGN_RECOMMENDATION` |

弃用字段策略：只标 `deprecated_in`，不删除；旧记录缺新字段一律按"缺失值语义"解释，不做回填。

### D.6 Analysis Content Identity vs Output Identity（必须分离）

**Analysis Content Identity** = 分析对象与输入的身份（不含 Parser/Adapter/Schema 实现）：

```text
analysis_content_identity =
  "aci-" + sha256(
      "identity-v2"
      || 0x00 || source_repository
      || 0x00 || source_commit            # 40-hex；短 SHA 先带标记降级
      || 0x00 || source_path
      || 0x00 || source_digest
      || 0x00 || input_digest
      || 0x00 || input_normalization_version
  )[:32]
```

| 项 | 决定 | 标注 |
|---|---|---|
| 必填 | `source_repository`、`source_path`、`input_digest`、`input_normalization_version` | `DESIGN_RECOMMENDATION` |
| 条件必填 | `source_commit`（provenance 完整时）、`source_digest`（source 存在时） | `DESIGN_RECOMMENDATION` |
| 可为空 | `source_digest`（MISSING）、`input_reference_offset`（UNALIGNED） | `DESIGN_RECOMMENDATION` |
| 包含 Parser Version？ | **不包含** | `DESIGN_RECOMMENDATION` |
| 包含 Adapter/Schema？ | **不包含** | `DESIGN_RECOMMENDATION` |
| 空值语义 | 缺失字段一律以**长度前缀 + 显式标记**（如 `"\x00MISSING"`）参与，禁止"空串拼接"造成 `a|b` 与 `a||b` 混淆 | `DESIGN_RECOMMENDATION` |
| 稳定性 | 同一输入源的逻辑身份在 Parser/Adapter/Schema 变化时**保持不变** | `DESIGN_RECOMMENDATION` |

**本阶段内存验证（`EVIDENCE_CONFIRMED`）：** 用 3 种候选字段组合对 34 条实测，均得 **34 个唯一身份、0 碰撞**：

| 候选 | 字段 | 唯一数 |
|---|---|---|
| C1 | repo + commit + path + input_digest | 34/34 |
| C2 | C1 + source_digest | 34/34 |
| C3 | repo + commit + path + source_digest | 34/34 |

推荐 **C2**（同时钉住"仓库内容"与"实际输入"）。

**Analysis Output Identity**（独立、不可用输入身份代替）：

```text
analysis_output_identity =
  "aoi-" + sha256(
      "output-v1"
      || 0x00 || canonical_json(record_without(volatile, identity, provenance_epoch))
  )[:32]
```

其中 `volatile = {created_at, reanalysis_timestamp, generated_at, executed_at, duration_ms}`（与 Batch B 的 `VOLATILE` 对齐，`EVIDENCE_CONFIRMED` 于 `reanalysis_176.py`），且**必须**剔除身份字段本身（否则自引用）。

**本阶段实测（`EVIDENCE_CONFIRMED`）：** 34 条记录 canonical 输出摘要 **34/34 唯一**，今天无"同输出"样本；`output_identity` 的碰撞/并列行为只能靠合成测试验证（见 L 节）。

---

## E. Stage C — Identity Contract Design

### E.1 三方案对比

| 维度 | A. Stable Content + Execution | B. Stable Analysis + Result | C. Layered（推荐） |
|---|---|---|---|
| 核心分层 | 2 层：content / execution | 2 层：analysis_id / result_id | 8–10 层（D 节全部） |
| 同输入不同 Build | 可区分（execution 不同） | 可区分（result 不同） | 可区分 |
| 保留旧 ID | 需额外映射 | 天然（analysis_id 不变） | 天然 + 显式 legacy 字段 |
| Linkage 指向 | 需决定指向 content 还是 execution | 指向 analysis_id（+ 目标 result 指针） | analysis_id（逻辑对象）+ `result_ref` |
| 历史结果保留 | 隐式（execution 集合） | 显式（result 集合） | 显式 |
| 下游改动量 | 中（需理解第二层） | 小（旧字段不动，新增 result） | 中（分层多，需 Resolver） |
| 风险 | "逻辑对象"缺失，Linkage 语义模糊 | execution/parser 身份被压进 result 内部，颗粒度不足 | 字段偏多，需严格去重规则 |

### E.2 推荐：C（分层）+ B 的结果模型

理由（`DESIGN_RECOMMENDATION`）：

1. 单独 A 缺少"哪个结果当前有效"的显式模型，而 150 条 Linkage 必须能指向**具体一次执行**。
2. 单独 B 缺少 Parser/Adapter/Schema 的独立身份，无法表达"实现变了但输出没变"。
3. C 的代价是字段多，但其中**只有 4 个进入哈希**（content、execution、output、schema），其余为 provenance，可避免"字段膨胀即哈希膨胀"。
4. **迁移成本最低**：`analysis_id` 语义从"ID"降级为"逻辑对象 ID"，旧值原样保留；新结果落在独立目录，旧 150 条 Linkage 一个字节都不用动。

### E.3 Identity Contract Table

`Hash Input` = 是否参与某个摘要计算；`Reanalysis Impact` = 变化时是否影响复用判定；`Historical Compatibility` = 对 34 条旧记录的处置。

| Field | Meaning | Required | Generated By | Hash Input | Reanalysis Impact | Historical Compatibility |
|---|---|---|---|---|---|---|
| `source_repository` | owner/repo 原样 | 是 | Adapter（metadata） | content | 变化 → 新对象 | 34/34 有值，保留 |
| `source_commit` | 40-hex commit | 是（provenance 完整时） | Adapter | content | 变化 → 新对象 | 34/34 有 full SHA |
| `source_commit_status` | `FULL`/`LEGACY_SHORT`/`UNKNOWN` | 是 | Adapter | 否（标记位） | 决定可信度 | 34/34 `FULL` |
| `source_path` | repo 相对 POSIX 路径 | 是 | Adapter | content | 变化 → 新对象 | 34/34 有值 |
| `source_digest` | pinned source 字节 sha256 | 条件 | Adapter | content | 变化 → REANALYZE | 34/34 有值 |
| `source_status` | `PRESENT`/`MISSING`/`SYMLINK` | 是 | Adapter | 否 | MISSING → 手工审查 | 34/34 `PRESENT`（推定，`NOT_VERIFIED` 逐条：脚本仅验证 34/34 文件存在） |
| `input_digest` | Reference 字节 sha256 | 是 | Adapter | content | 变化 → REANALYZE | 34/34 有值且与文件一致 |
| `input_normalization_version` | `bytes-v1` | 是 | 常量 | content | 变化 → REANALYZE | 旧记录缺省 → `LEGACY_UNVERIFIED`（不猜测） |
| `input_reference_offset` | Reference 相对 source 的前导行数 | 否（可为 null） | Adapter | 否 | 影响行号可信度 | 34/34 有该字段 |
| `input_mapping_status` | `ALIGNED`/`UNALIGNED` | 是 | Adapter | 否 | UNALIGNED → 禁止行号提升 | 派生自 `source_consistent` |
| `parser_name` | `gd_parse` | 是 | 常量 | execution | 变化 → 新工具链 | 34/34 有值 |
| `parser_version` | 声明协议版本 | 是 | 常量 | execution（不是 content） | 变化 → 评估影响 | 34/34 `1.71` |
| `parser_build_identity` | 实现身份 `gd_parse@<v>+build:<16>` | 是（新记录） | Builder | execution | 变化 → 评估影响 | **34/34 缺失** → `NOT_AVAILABLE`，禁止回填 |
| `parser_contract_version` | 输出契约版本 | 是（新记录） | 常量 | execution | 变化 → REANALYZE/REVALIDATE | 缺失 → `LEGACY_UNVERIFIED` |
| `parser_build_status` | `VERIFIED`/`DIRTY`/`UNKNOWN` | 是 | Builder | 否（标记位） | UNKNOWN → 手工审查 | 旧记录 → `NOT_AVAILABLE` |
| `adapter_version` | Adapter 声明版本 | 是（新记录） | 常量 | execution | 评估影响 | 缺失 → `NOT_AVAILABLE` |
| `adapter_build_identity` | Adapter 实现身份 | 是（新记录） | Builder | execution | 评估影响 | 缺失 → `NOT_AVAILABLE` |
| `adapter_contract_version` | 记录投影契约版本 | 是（新记录） | 常量 | execution | 变化 → MIGRATION/REVALIDATE | 缺失 → `LEGACY_UNVERIFIED` |
| `analysis_schema_version` | 记录结构版本 | 是 | 常量 | execution | 变化 → MIGRATION | 34/34 = 1 |
| `analysis_schema_identity` | Schema 契约摘要 | 是（新记录） | 常量/计算 | execution | 变化 → MIGRATION | 缺失 → `NOT_AVAILABLE` |
| `analysis_content_identity` | 输入对象身份 | 是（新记录） | 计算 | 被引用 | 变化 → 新对象 | 34/34 可回算（C2 实验） |
| `analysis_execution_identity` | 一次执行的身份 | 是（新记录） | 计算 | 被引用 | 变化 → 新结果 | 34/34 只能得 `LEGACY_UNVERIFIED`（无 build） |
| `analysis_output_identity` | 输出内容身份 | 是（新记录） | 计算 | 被引用 | 变化 → 冲突/新结果 | 34/34 可回算（实测唯一） |
| `analysis_id` | 逻辑分析对象 ID（旧值保留） | 是 | 现有公式（冻结） | 否（键） | 不变 | 34/34 原样保留 |
| `identity_version` | 身份契约版本（`1`=legacy，`2`=本契约） | 是 | 常量 | 否 | 决定字段解释 | 34 条 = `1`（推定）→ `LEGACY_UNVERIFIED` |
| `identity_status` | `VERIFIED`/`LEGACY_UNVERIFIED`/`NOT_AVAILABLE`/`UNKNOWN` | 是 | 计算 | 否 | 决定可否复用/作为 Current | 34 条 → `NOT_AVAILABLE`（build 无从重建） |
| `record_id` | 记录实例 ID（= `result_id`） | 是（新写入） | 计算 | 否（键） | 不变 | 旧记录无 → 以文件 sha256 兜底 |
| `supersedes` | 被替代的 `record_id`/null | 否 | 调用方 | 否 | 影响 Current 选择 | 旧记录 null |
| `result_status` | `GENERATED`/`VALIDATED`/`ACCEPTED`/`SUPERSEDED`/`REJECTED`/`QUARANTINED` | 是（新写入） | 流程 | 否 | 决定能否作为 Current | 旧记录 → `ACCEPTED`（既有事实，不是新判定） |

`analysis_execution_identity` 公式：

```text
analysis_execution_identity =
  "aei-" + sha256(
      "exec-v1" || 0x00 || analysis_content_identity
      || 0x00 || parser_name || 0x00 || parser_version
      || 0x00 || parser_build_identity || 0x00 || parser_contract_version
      || 0x00 || adapter_build_identity || 0x00 || adapter_contract_version
      || 0x00 || analysis_schema_identity
      || 0x00 || runtime_fingerprint
  )[:32]
```

`runtime_fingerprint = "python:<major.minor>|<platform_system>"`（当前实测 `3.12.10` / `Windows`）。**本阶段实测闭包不读环境变量（N-7）**，故不登记 env；若将来引入 env 依赖，必须递增 `runtime_fingerprint` 版本前缀。

---

## F. Stage D — Build Identity Generation & Verification

### F.1 四种生成方式对比

| 方案 | 优点 | 致命缺陷 | 判定 |
|---|---|---|---|
| 1. Git Commit Hash | 免费、可审计 | HEAD 不变而工作区已改（本阶段实测 31 内容差异 + 4 stat-only）；未跟踪文件不在 HEAD；Adapter 未提交 | **不可单独使用** |
| 2. 相关源码文件 SHA-256（单文件） | 简单、反映实际字节 | 无法表达多文件依赖闭包（`paths.py` 被漏掉即 N-6） | 需扩展为 3 |
| 3. 确定性 Manifest Hash（多文件路径+摘要） | 反映实际执行代码、可复算、顺序无关 | 需明确闭包与规范化规则 | **推荐主体** |
| 4. 源码 + 配置 + 运行时依赖组合 | 最完整 | 过度哈希：Python 解释器/标准库升级会让所有记录"身份变化"，噪声大于信号 | **仅作 provenance，不进哈希** |

结论（`DESIGN_RECOMMENDATION`）：**主身份用方案 3**（源码闭包 manifest），**运行时指纹**作为独立字段（`runtime_fingerprint`）记录但**不进** Parser Build Identity，只进 `analysis_execution_identity`。

**为什么不能只信 Git（`EVIDENCE_CONFIRMED` 实测）：**

- 当前实构建 `gd_parse@1.75+build:3b36069a44beb55c` ≠ Batch B 记录的 `…6b74a6cd20a06033`，而两者 `HEAD` 完全相同（`d64b1cd5…`）→ 同 HEAD、不同实现，真实存在。
- 本阶段 `git status` 显示 `gd_parse.py` 处于 ` M`（内容已改、未提交）→ Git 视角"版本未变"，实际执行代码已变。
- 存在 593 个未跟踪文件；若 Parser 依赖其中任何一个（如新增模块），Git 完全不可见。

### F.2 Build Manifest 设计（示例，不创建文件）

```json
{
  "identity_format": "phase-1.78/1",
  "component": "gd_parse",
  "component_version_field": "parser_version",
  "declared_version": "1.75",
  "source_files": [
    {"path": ".ai/tools/learning/gd_parse.py", "sha256": "<64hex>"}
  ],
  "dependency_manifest": [
    {"path": ".ai/tools/learning/paths.py", "sha256": "<64hex>", "role": "parser_dependency"}
  ],
  "excluded": [
    {"path": ".ai/tools/learning/tests/*", "reason": "test_only"},
    {"path": ".ai/tools/learning/__pycache__/*", "reason": "generated"}
  ],
  "source_digest": "<64hex: sha256 of canonical file list>",
  "configuration_digest": null,
  "runtime_fingerprint": {"python": "3.12", "platform": "Windows"},
  "build_identity": "gd_parse@1.75+build:<16hex>",
  "build_status": "VERIFIED",
  "git_head": "d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84",
  "workspace_state": "DIRTY"
}
```

| 规则 | 定义 | 标注 |
|---|---|---|
| 文件清单确定方式 | **显式登记**，不由"扫描整个 tools 目录"推导。Parser 闭包 = `gd_parse.py` + 其递归 import 的本项目模块（当前为空）；Adapter 闭包 = `external_code_understanding.py` + `source_analysis.py` + `provenance.py` + `paths.py` | `DESIGN_RECOMMENDATION`（依据 N-6 / N-7） |
| 顺序规范化 | 按 `path` 的 POSIX 形式做**字节序**排序后拼接 | `DESIGN_RECOMMENDATION` |
| 路径规范化 | 相对 Project Root、POSIX `/`、小写盘符不出现、不解析符号链接 | `DESIGN_RECOMMENDATION` |
| 摘要算法 | 每个文件 `sha256(bytes)`；组合 `sha256( join("\0", path + ":" + file_sha256) )`；`build_identity` 取组合摘要前 16 hex，格式 `gd_parse@<declared_version>+build:<16hex>`（与现有格式兼容） | `DESIGN_RECOMMENDATION` |
| 排除项 | `__pycache__`、`*.pyc`、tests、`.ai/tmp`、文档、任何非执行输入 | `DESIGN_RECOMMENDATION` |
| 未跟踪相关文件 | **必须包含**：未跟踪但属闭包 → 计入 manifest，且 `workspace_state=DIRTY_UNTRACKED` | `DESIGN_RECOMMENDATION` |
| Git 忽略文件 | 若属闭包且存在 → 计入并标 `ignored=true`（不得静默忽略），因为 Python 会照常 import | `DESIGN_RECOMMENDATION` |
| Manifest 不完整检测 | 闭包内任一文件缺失、或发现 `import` 目标不在 manifest → `build_status=UNKNOWN`，禁止写入正式路径 | `DESIGN_RECOMMENDATION` |
| 可重复性 | 同字节同平台 → 同身份；跨平台差异只来自 `runtime_fingerprint`，不进 Build Identity | `DESIGN_RECOMMENDATION` |

### F.3 Build Identity Verification

| 验证 | 设计 | 标注 |
|---|---|---|
| 可从 Manifest 复算 | `validate_identity_manifest()` 重算每个 `file_sha256` 与组合摘要，不一致即拒绝 | `DESIGN_RECOMMENDATION` |
| 源码变化 → 身份变化 | 差分测试（改一个字节 → 身份必须变） | `DESIGN_RECOMMENDATION` |
| 文件顺序变化不影响 | 打乱 manifest 顺序 → 身份不变 | `DESIGN_RECOMMENDATION` |
| 路径规范化确定性 | `.\a\b.py` / `a/b.py` / `A/B.py`(Windows) 规则明确；Windows 上路径比较按 `casefold`，但 manifest 存原样 | `DESIGN_RECOMMENDATION`（`OPEN_QUESTION`：是否接受 Windows 大小写不敏感带来的歧义） |
| 未知依赖不得静默忽略 | 闭包解析失败 → `UNKNOWN`，不降级为"仅哈希主文件" | `DESIGN_RECOMMENDATION` |
| 无法确认 → `UNKNOWN` | `build_status` 三态：`VERIFIED`/`DIRTY`/`UNKNOWN` | `DESIGN_RECOMMENDATION` |
| **人工填写不被接受** | `build_identity` 只允许由 `compute_*_build_identity()` 写入；校验时重算并与声明比对，不一致 → 拒绝写入（Guard 3） | `DESIGN_RECOMMENDATION` |

**核心原则（`DESIGN_RECOMMENDATION`）：** Build Identity 必须反映**实际被 import 并执行的代码**，而不是"声明的版本"。因此它由运行时在**写入记录的那一刻**计算，并随记录持久化；事后再"补录"必须重算并标注 `computed_at` 与 `workspace_state`。

### F.4 Dirty Workspace 分类

| 情况 | `build_status` | `workspace_state` | 是否允许写正式路径 | 标注 |
|---|---|---|---|---|
| Clean（闭包全部 tracked 且无改动） | `VERIFIED` | `CLEAN` | 允许 | `DESIGN_RECOMMENDATION` |
| 已跟踪闭包文件被修改 | `DIRTY` | `DIRTY_TRACKED` | **默认拒绝**；仅隔离工作区允许 | `DESIGN_RECOMMENDATION` |
| 未跟踪的**相关**文件（闭包内/被 import） | `DIRTY`（身份仍确定，但不可复现于任何 commit） | `DIRTY_UNTRACKED_RELEVANT` | 仅隔离工作区 | `DESIGN_RECOMMENDATION` |
| 未跟踪的**无关**文件 | 不影响身份 | `CLEAN` | 允许 | `DESIGN_RECOMMENDATION` |
| 被忽略但相关的文件 | `DIRTY` | `IGNORED_RELEVANT` | 仅隔离工作区 | `DESIGN_RECOMMENDATION` |
| 依赖闭包变化（如 `paths.py` 改） | `VERIFIED`（新身份）或 `DIRTY` | `CLEAN`/`DIRTY_*` | 身份已变，须走 Reanalysis 判定 | `DESIGN_RECOMMENDATION` |

**当前实测状态（`EVIDENCE_CONFIRMED`）：** `gd_parse.py` 为 ` M` 且未提交 → 今天若写正式记录，`workspace_state` 必为 `DIRTY_TRACKED`，按上表**应当被拒绝**。这正是 Phase 1.78 之前所有 Batch 都必须用"隔离 workspace"的原因，也是守卫必须区分"隔离 vs 正式"的依据。

---

## G. Stage E — Legacy Analysis ID & Backward Compatibility

### G.1 旧 ID 保留策略

```text
analysis_id            # 逻辑分析对象 ID：34 条旧值原样、永不重算
canonical_analysis_id  # 新契约下的 content identity 派生 ID（新对象才生成）
legacy_analysis_id     # 显式记录"这条记录的旧 ID 是什么"（新记录引用旧结果时必填）
identity_version       # 1 = legacy 契约；2 = 本契约
identity_status        # VERIFIED / LEGACY_UNVERIFIED / NOT_AVAILABLE / UNKNOWN
```

| 规则 | 设计 | 标注 |
|---|---|---|
| 永久保留旧 ID | 是。`analysis_id` 冻结；`legacy_analysis_id` 仅在新记录**替代/引用**旧结果时填写 | `DESIGN_RECOMMENDATION` |
| 新 ID 映射旧 ID | 通过 `legacy_analysis_id` + Resolver（M.4），不做全局重写 | `DESIGN_RECOMMENDATION` |
| 多 legacy → 一 canonical | 允许（历史上重复采集同一对象时），但必须 `identity_status` 一致且输出摘要一致；否则 `AMBIGUOUS_LEGACY_MAPPING` | `DESIGN_RECOMMENDATION` |
| 一 canonical → 多执行 | 允许（这正是 Result 模型的目的） | `DESIGN_RECOMMENDATION` |
| 映射验证 | 复算 `canonical_analysis_id` 与 `analysis_content_identity` 一致、且 `legacy_analysis_id` 在旧集合中存在 | `DESIGN_RECOMMENDATION` |
| 映射冲突 | 两 legacy 指向同一 canonical 但输出摘要不同 → 拒绝自动合并，进人工审查 | `DESIGN_RECOMMENDATION` |

### G.2 150 条 Linkage 兼容（最高优先）

事实（`EVIDENCE_CONFIRMED`）：

- 150 条 `linkage_id = "lnk-" + sha256("phase-1.73-b|<analysis_id>|<feature_id>")[:16]`，复算 150/150；
- 每条 Linkage 内嵌 `external_analysis.analysis_record_path` + `analysis_record_digest`（Analysis 文件**原始字节** sha256，含 CRLF 影响）；
- `verify_record_sources()` 在写入/校验时**强制**比对当前文件字节；`evaluate_freshness()` 不一致 → `STALE`；
- 150 条引用 34 条记录，**悬挂 0**；覆盖 5 个 Feature（`health`、`health_bar`、`blackboard`、`openable_door`、`attack_emitter`）；
- `analysis_id` 被当**文件名**使用（`evidence_impact_176.py:757`、`manual_evidence_review_176.py:654`）。

**结论（`EVIDENCE_CONFIRMED`）：** 任何"就地给 34 条记录加字段"的方案都会把 150 条 Linkage 全部打成 STALE，并让 3 个 Candidate 的 `linkage_record_digest` 链失效。**必须禁止就地迁移。**

**过渡方案（推荐，`DESIGN_RECOMMENDATION`）— "旁挂身份 + 只读锚定"：**

1. 34 条旧记录**字节不动**（`analysis_id`、文件路径、CRLF 全部保留），状态标 `identity_status=NOT_AVAILABLE`。
2. 新建旁挂文件 `.ai/learning/external_code/identity/legacy_identity.json`（未来阶段才创建）：为每条 `analysis_id` 记录**可复算**的身份（`analysis_content_identity`、`analysis_output_identity`、`identity_status`、`evidence_note="build identity cannot be reconstructed"`），**不写回**记录。
3. Linkage 不改：`analysis_record_digest` 依然匹配（记录字节未变）。
4. 新执行走新目录（`records/v2/<analysis_id>/<result_id>.json`），旧目录保持只读。
5. 若将来必须重跑 34 条：新结果以 `supersedes` 指向旧 `analysis_id` 的 `record_id`（旧记录以文件 sha256 作兜底 `record_id`），旧 Linkage 继续有效；**是否升级 Linkage 指向新结果**需单独授权（`OPEN_QUESTION`）。
6. **禁止**：批量替换 ID、重建 150 条 Linkage、改写 `analysis_record_digest`、删除旧记录。

### G.3 Historical Unknown Identity 状态语义

| 状态 | 含义 | 进入条件 | 允许下游消费 | 允许复用 | 必须人工审查 |
|---|---|---|---|---|---|
| `VERIFIED` | 身份完整且可复算（build 已记录且复算一致） | 新写入且 `build_status=VERIFIED` | 是 | 是 | 否 |
| `LEGACY_UNVERIFIED` | 声明版本存在，实现身份缺失或不可复算 | 有 `parser_version` 无 `parser_build_identity` | 是（作为历史证据，标注限制） | 否（不得作为"已验证"复用） | 需要复用/升级时 |
| `NOT_AVAILABLE` | 关键身份字段从未记录且**不可能**重建 | 34 条记录（1.71 build 不可重建） | 是（只读证据） | 否 | 是（任何提升） |
| `UNKNOWN` | 存在但无法判定（如 manifest 不完整、校验失败） | 校验失败/闭包缺失 | **否**（写正式路径被 Guard 拒绝） | 否 | 是 |

**铁律（`DESIGN_RECOMMENDATION`）：** **不得**用 `parser_version` 反推 `parser_build_identity`。1.71 的源码字节已不存在（当前工作区 1.75，HEAD 更早），任何"1.71 = 某 build"的映射都是伪造 provenance。

### G.4 Migration Model（设计，不执行）

| 步骤 | 内容 | 前置 | 验证 | 回滚 |
|---|---|---|---|---|
| M1 | 生成旁挂 `legacy_identity.json`（只读派生） | 旧记录字节快照 | 34 条 content/output identity 可复算且唯一 | 删除旁挂文件 |
| M2 | 在 `index.json` **新增** `identity_status` 字段（可选字段，不重排） | M1 | 重建索引后 34 条 ID 集合不变 | 恢复旧索引字节 |
| M3 | 新契约记录写入新目录 | 写入守卫（H）就绪 | Guard 全绿；旧目录 0 字节变化 | 删除新目录 |
| M4 | Linkage 指向新结果的**可选**升级 | 单独授权 | 新旧 Linkage 并存且旧链接仍 FRESH | 保留旧 Linkage |

一致性保障：每一步都要求"旧受保护清单哈希不变"作为硬门禁（与 Batch E 方案一致）。**部分迁移检测**：以"旧清单哈希 + 新目录完整性"双条件判定，任一不满足即 `MIGRATION_PARTIAL` 并停止。

---

## H. Stage F — Write Protection Architecture

### H.1 Current Behavior（`EVIDENCE_CONFIRMED`）

| 项 | 实测 |
|---|---|
| 写入路径 | `ANALYSIS_DIR / ("%s.json" % record["analysis_id"])`，或 `--out-dir` 指定目录 |
| 文件名生成 | 完全由 `analysis_id` 决定（`ext-<16hex>.json`） |
| 同名文件处理 | `Path.write_text(...)` **直接覆盖**；无检查 |
| 原子写入 | **无**（无临时文件、无 `os.replace`） |
| 内容校验 | **无**（不校验输出摘要、不重新读取） |
| ID 冲突检测 | **无** |
| 历史记录保留 | **无**（无 `supersedes`、无版本后缀） |
| 覆盖授权 | **无** |
| 隔离模拟 | 同一 `analysis_id` 写两次 → 同一路径、内容被覆盖、目录仅 1 文件 |
| 调用方枚举（Stop #5） | 仅 2 处：`external_code_understanding.main()`（`:480`）+ `tests/test_batch_b.py:127-128`。**无其他生产调用方** |
| 已有正例 | `write_linkage()`：validate → `tempfile.mkstemp` → 重新读取并再校验 → `os.replace`；异常时 `unlink` 临时文件 |

### H.2 Write Guards（7 条）

| Guard | 规则 | 失败动作 | 标注 |
|---|---|---|---|
| **G1 Existing Record Protection** | 目标路径已存在 → 默认拒绝覆盖 | `WriteRejected(EXISTING_RECORD)` | `DESIGN_RECOMMENDATION` |
| **G2 Identity Consistency** | `文件名 ID` == `record.analysis_id` == `recompute(analysis_content_identity 派生)` 三者一致；且 `record_id` 可复算 | 拒绝 | `DESIGN_RECOMMENDATION` |
| **G3 Build Identity Consistency** | 记录声明的 `parser_build_identity`/`adapter_build_identity` == 当前运行复算值 | 拒绝（`BUILD_MISMATCH`） | `DESIGN_RECOMMENDATION` |
| **G4 Output Conflict** | 同一 `analysis_content_identity` 已有结果，且 `analysis_output_identity` 不同 → 进入冲突流程，**不得**静默覆盖 | `CONFLICT_REVIEW` | `DESIGN_RECOMMENDATION` |
| **G5 Historical Record Protection** | 旧目录（`analysis/`）与 `identity_status != VERIFIED` 的记录默认只读；`write_record` 禁用该目录 | 拒绝 | `DESIGN_RECOMMENDATION` |
| **G6 Explicit Replacement Authorization** | 覆盖必须携带独立授权凭据（`replacement_authorization`：授权人、理由、目标 `record_id`、旧摘要、新摘要、时间） | 无凭据 → 拒绝；有凭据 → 审计留痕 | `DESIGN_RECOMMENDATION` |
| **G7 Partial Write Protection** | 临时文件 + 写完重读校验 + `os.replace` + 失败 `unlink` + 中断残留检测（`.tmp` 前缀扫描） | 残留 → 拒绝启动/告警 | `DESIGN_RECOMMENDATION` |

**补充 Guard（源自本阶段发现）：**

| Guard | 规则 | 依据 |
|---|---|---|
| **G8 Canonical Serialization** | 写入使用 `json.dumps(sort_keys=True, indent=2)` + **显式 `newline="\n"`**；`file_sha256` 与 `content_sha256` 分开记录 | N-1/N-2/N-3（CRLF 导致跨平台摘要漂移） |
| **G9 Scope Guard** | 正式路径写入要求 `workspace_state` ∈ {`CLEAN`}；`DIRTY_*` 只能写隔离工作区 | F.4 |

### H.3 Write Operation Classification

| 操作 | 前置条件 | 结果 | 审计要求 | 标注 |
|---|---|---|---|---|
| `CREATE_NEW` | 目标不存在；身份/build 校验通过；Scope Guard 通过 | 新建记录 | 记录 build manifest 引用、`workspace_state` | `DESIGN_RECOMMENDATION` |
| `REUSE_IDENTICAL` | 目标存在；`analysis_content_identity` + `analysis_execution_identity` + `analysis_output_identity` 全一致 | 不写盘，返回既有路径 | 仅计数；**必须允许**，否则 `test_batch_b` 的幂等断言失败（N-4） | `DESIGN_RECOMMENDATION` |
| `REJECT_CONFLICT` | 目标存在但身份不符 | 拒绝并返回差异字段 | 记录冲突详情 | `DESIGN_RECOMMENDATION` |
| `CREATE_NEW_RESULT` | 同一 content identity，不同 execution identity | 新 `record_id`，`supersedes` 指向旧 | 记录 reanalysis reason / 触发身份 | `DESIGN_RECOMMENDATION` |
| `MIGRATE_METADATA` | 仅记录结构/投影字段变化，输出摘要不变 | **写新结果副本**，不原地改 | 记录 migration 版本对 | `DESIGN_RECOMMENDATION` |
| `AUTHORIZED_REPLACE` | G6 凭据齐全 + 人工确认 | 覆盖，旧字节归档 | 全量审计（谁/为何/前后摘要） | `DESIGN_RECOMMENDATION`（`OPEN_QUESTION`：授权凭据格式与保管责任） |

### H.4 Write Guard Decision Matrix

| Target Exists | Identity Match | Build Match | Output Match | Operation |
|---|---|---|---|---|
| No | N/A | `VERIFIED` | N/A | `CREATE_NEW` |
| No | N/A | `DIRTY`/`UNKNOWN` | N/A | `REJECT`（仅隔离工作区可写） |
| Yes | Yes | Yes | Yes | `REUSE_IDENTICAL` |
| Yes | Yes | Yes | **No** | `CONFLICT_REVIEW`（**非确定性**：同 build 同输入不同输出，禁止当新结果） |
| Yes | Yes | No | No | `CREATE_NEW_RESULT` |
| Yes | Yes | No | Yes（输出意外相同） | `CREATE_NEW_RESULT` + 标注 `OUTPUT_UNCHANGED_BY_BUILD` |
| Yes | No | Any | Any | `REJECT_CONFLICT` |
| Yes | Unknown | Unknown | Unknown | `MANUAL_REVIEW` |
| Yes | Any | Any | Any | `AUTHORIZED_REPLACE`（仅 G6 凭据） |

额外边界（本阶段补充）：

| 场景 | 处理 |
|---|---|
| 目标存在但**无法解析**（半成品/损坏 JSON） | `QUARANTINE`：拒绝覆盖，移入隔离区需授权；不得静默重写 |
| 目标存在且 `identity_status=NOT_AVAILABLE`（34 条） | 只读；任何写入 → `HISTORICAL_READ_ONLY` |
| 目标目录不存在 | `CREATE_NEW` 可建目录；但**不得**在旧受保护目录内建新文件 |
| 同一 `record_id` 出现在两个文件 | `DUPLICATE_RECORD_ID` → 全量拒绝写入，需人工处理 |

三类操作**不得合并**：`CREATE_NEW_RESULT`（并存新结果）、`MIGRATE_METADATA`（结构迁移，不改语义）、`AUTHORIZED_REPLACE`（真正覆盖）。

---

## I. Stage G — Immutable Analysis Result Model

### I.1 结果字段（候选设计，不加入正式 Schema）

```text
record_id                     # "rec-" + sha256(execution_identity)[:16]
analysis_id                   # 逻辑对象（旧值保留）
analysis_content_identity
analysis_execution_identity
analysis_output_identity
parser_build_identity / adapter_build_identity / analysis_schema_identity
result_status                 # GENERATED / VALIDATED / ACCEPTED / SUPERSEDED / REJECTED / QUARANTINED
supersedes                    # 前一个 record_id（或 null）
superseded_by                 # 反向指针（由后写者维护，索引层即可）
reanalysis_reason             # SOURCE_CHANGED / PARSER_BUILD_CHANGED / PARSER_CONTRACT_CHANGED /
                              # ADAPTER_CHANGED / SCHEMA_CHANGED / MANUAL_REVIEW / PILOT
execution_timestamp           # 仅供审计，不参与 Current 选择
build_manifest_ref            # 到 manifest 文件的相对路径 + manifest sha256
validation                    # {determinism, locations, provenance, coverage, reviewer}
```

### I.2 Current Result Selection（拒绝"时间戳最新即有效"）

| 问题 | 设计答案 | 标注 |
|---|---|---|
| 最新结果一定有效？ | **否**。必须 `result_status ∈ {VALIDATED, ACCEPTED}` | `DESIGN_RECOMMENDATION` |
| Build 未验证能否成为 Current？ | **否**。`build_status=VERIFIED` 是必要条件 | `DESIGN_RECOMMENDATION` |
| Coverage PARTIAL 能否成为 Current？ | **可以**，但必须携带 `syntax_coverage_status` + `analysis_completeness` 并在下游显示；PARTIAL 不得**替代** COMPLETE 旧结果除非人工接受 | `DESIGN_RECOMMENDATION` |
| 未通过验证的 Reanalysis 能否替代旧结果？ | **否**（`REJECTED`/`QUARANTINED` 不参与 Current） | `DESIGN_RECOMMENDATION` |
| 是否需要人工验收？ | 是：首次提升、跨 contract 版本、冲突解决三类必须人工 | `DESIGN_RECOMMENDATION` |
| 旧结果能否恢复为 Current？ | 是（把当前 result 标 `SUPERSEDED`，旧 result 改 `ACCEPTED`），需审计 | `DESIGN_RECOMMENDATION` |

排序规则（非时间）：

```text
current = argmax over results of tuple(
    result_status_rank,        # ACCEPTED(3) > VALIDATED(2) > GENERATED(1) > others(0)
    contract_rank,             # 与当前 parser_contract_version 一致优先
    coverage_rank,             # COMPLETE(2) > PARTIAL(1) > UNKNOWN(0)
    -execution_seq             # 同分时取较晚执行（仅作最后 tie-break）
)
```

### I.3 Result State Model

```text
GENERATED ──validate_ok──> VALIDATED ──human_accept──> ACCEPTED ──newer_accepted──> SUPERSEDED
    │                          │                          │
    └──validate_fail──> REJECTED（不可恢复，需新执行）
                               │
                        conflict/uncertain ──> QUARANTINED ──review──> {VALIDATED, REJECTED}
```

| 状态 | 进入条件 | 可作 Current | 可复用 |
|---|---|---|---|
| `GENERATED` | 刚写盘 | 否 | 否 |
| `VALIDATED` | 确定性 + 位置 + provenance + build 校验通过 | 是（优先级低于 ACCEPTED） | 是 |
| `ACCEPTED` | 人工接受（或既有事实的历史记录） | 是 | 是 |
| `SUPERSEDED` | 被更新的 ACCEPTED 替代 | 否 | 是（可恢复） |
| `REJECTED` | 校验失败/非确定性 | 否 | 否 |
| `QUARANTINED` | 冲突或身份不明 | 否 | 否（需审查） |

---

## J. Stage H — Identity & Reanalysis Decision Contract

### J.1 变化 → 动作总表

| 变化组件 | 推荐动作 | 理由 | 标注 |
|---|---|---|---|
| `source_digest` | **REANALYZE** | 实际源内容变了 | `DESIGN_RECOMMENDATION` |
| `input_digest` | **REANALYZE** | Parser 输入变了 | `DESIGN_RECOMMENDATION` |
| `parser_build_identity` | **EVALUATE_PARSER_IMPACT**（非自动重跑） | 实现变化未必改变输出（见 J.2） | `DESIGN_RECOMMENDATION` |
| `parser_contract_version` | **REANALYZE 或 REVALIDATE** | 契约变化可能只影响元数据 | `DESIGN_RECOMMENDATION` |
| `adapter_build_identity` | **EVALUATE_ADAPTER_IMPACT** | 投影逻辑变化不一定改 Parser 输出 | `DESIGN_RECOMMENDATION` |
| `adapter_contract_version` | **RECORD_MIGRATION / REVALIDATE** | 结构变化按新 Schema 重投影 | `DESIGN_RECOMMENDATION` |
| `analysis_schema_version` | **SCHEMA_MIGRATION / VALIDATION** | 不改 Parser 输出 | `DESIGN_RECOMMENDATION` |
| `runtime_fingerprint` | **EVALUATE_REPRODUCIBILITY** | 只影响可复现性，不自动重跑 | `DESIGN_RECOMMENDATION` |
| provenance 缺失/不可复算 | **MANUAL_REVIEW** | 不得猜测 | `DESIGN_RECOMMENDATION` |

### J.2 八种具体情形（任务书要求的逐条判定）

| # | 情形 | 判定 | 依据 | 标注 |
|---|---|---|---|---|
| 1 | Parser 实现变化，输出**完全相同** | `REUSE_OUTPUT`（保留旧结果为 Current，登记新 execution 身份为"已验证等价"） | 输出摘要是判据，不是 build | `DESIGN_RECOMMENDATION` |
| 2 | Parser 实现变化，Symbol 输出不同 | `REANALYZE` → `CREATE_NEW_RESULT`（旧结果 SUPERSEDED 需人工接受） | 影响下游证据 | `DESIGN_RECOMMENDATION` |
| 3 | Parser 实现变化，仅 Coverage 元数据不同 | `REANALYZE`（轻量）→ 新结果；**不**自动替代旧结果作为 Current | Batch E 正是此类（COMPLETE→PARTIAL） | `EVIDENCE_CONFIRMED`（Batch E 事实）+ `DESIGN_RECOMMENDATION`（策略） |
| 4 | Adapter 变化，Parser 输出相同 | `RECORD_MIGRATION`（重新投影），不重跑 Parser | Parser 输出可复用 | `DESIGN_RECOMMENDATION` |
| 5 | Schema 变化，语义不变 | `SCHEMA_MIGRATION` | 只改结构 | `DESIGN_RECOMMENDATION` |
| 6 | `source_digest` 变但 commit 未变 | `REANALYZE` + `PROVENANCE_ALERT`（本地源被改写，commit 不可信） | 说明 pinned source 被本地修改 | `DESIGN_RECOMMENDATION` |
| 7 | Build 缺失但 `parser_version` 存在（34 条） | `LEGACY_UNVERIFIED`：只读消费；任何复用/提升 → `MANUAL_REVIEW` | 不可反推 | `EVIDENCE_CONFIRMED`（34/34 缺失） |
| 8 | Build Manifest 无法完整复算 | `UNKNOWN`：禁止写正式路径；进 `QUARANTINED`/`MANUAL_REVIEW` | 不允许"降级哈希" | `DESIGN_RECOMMENDATION` |

**明确反对的规则（`DESIGN_RECOMMENDATION`）：** "任何 build 变化都必须重分析"。反例即情形 1（Batch E 后仍有输出不变的记录）与情形 4（Adapter 变化不改 Parser 输出）。

---

## K. Stage I — Downstream Identity Compatibility

### K.1 实测依赖（`EVIDENCE_CONFIRMED`）

| Consumer | 现有依赖 | 证据 |
|---|---|---|
| Analysis 存储/索引 | `analysis_id` 作为文件名与索引键；`index.json` 34 条与记录集合 34/34 一致；索引条目**不含** `parser_version`/build | `external_code_understanding.build_index()`；`index.json` 键清单 |
| Linkage（`feature_linkage.py`） | `analysis_id` + `analysis_record_path` + `analysis_record_digest` + `linkage_id`；写入时 `verify_record_sources()` 强制比对文件字节 | `:1067`、`:1120-1135` |
| Candidate Eligibility | `analysis_id`、`analysis_record_digest`、`linkage_record_digest`、`source_digest`、`source_commit` | `candidate_eligibility.py:431-450` |
| Candidate Workspace | `candidate_id`（`cand-<16hex>`）+ `content_digest`；seeds 引用 `linkage_id` + `analysis_id` + 摘要 | `WORKSPACE.json`、`candidate_workspace.py:395-405` |
| Seed Policy | 仅 `linkage_id` 键；**无** parser/coverage 门禁 | `candidate_seed_policy.json`；`evidence_impact_176.py:808-830` |
| Graph | 无 `analysis_id`/`ext-` 引用（Phase 1.77 结论，本阶段未再核；`feature_graph.json` 为 Feature 级） | `NOT_VERIFIED`（本阶段未重跑该检查） |
| Review / Impact | `evidence_impact_176.py:756-763` 计算 `analysis_record_digest_matches`、`source_digest_matches`、`commit_matches`、`linkage_digest_matches`；`manual_evidence_review_176.py:870-873` 复算摘要 | 源码 |
| Reanalysis 工具 | `EXPECTED_IDENTITY` 硬门禁（`:51,:236`）；`PARSER_VERSION` 比较（`:503`） | 源码 |
| Provenance / Digest Validator | `provenance_validator.py` 只校验仓库/Reference/Catalog，**不读** Analysis ID；无 build 概念 | 源码 |
| `search_assets.py` | 用 `analysis_id` 关联分析摘要（`:165,:247`） | 源码 |

### K.2 兼容矩阵

| Consumer | Current Identity Dependency | Proposed Identity Dependency | Migration Required | Risk |
|---|---|---|---|---|
| Analysis Index | `analysis_id`（键） | `analysis_id` + `identity_status` + `parser_build_identity` | 低（只增字段） | 索引重建会刷新 `generated_at`，但记录字节不变 |
| Linkage | `analysis_id` + **文件字节 digest** | 不变 + 可选 `result_ref` | **禁止**（本阶段）；未来需授权 | 记录字节任何变化 → 150 条 STALE（高） |
| Candidate Eligibility | `analysis_id` + 双层 digest | 不变 + `identity_status` 门禁 | 低 | 若未来新结果替换，seed 指向需人工 |
| Candidate Workspace | `linkage_id` + digest 链 | 不变 | 无 | 链式失效风险（中） |
| Seed Policy | `linkage_id` | 需新增 `parser_build_identity`/`coverage` 显式门禁 | 是（未来阶段） | 无门禁 → 新结果可能被隐性拒绝或误用（中） |
| Review / Impact | 摘要比对 | 增加 build/identity 字段比对 | 低 | 摘要口径（CRLF/LF）不一致会误报（中） |
| Reanalysis 工具 | 硬编码 `EXPECTED_IDENTITY` | 改为"接受 manifest 校验通过的任意 build"+ 记录实际 build | 是 | 硬门禁会阻止合法新 build（中） |
| Provenance Validator | 无 | 可增加 `identity_status` 摘要校验 | 低 | 无 |
| Graph | 无引用 | 不变 | 无 | 无 |

### K.3 六个必答问题

| # | 问题 | 答案 | 标注 |
|---|---|---|---|
| 1 | 哪些必须继续识别 Legacy ID？ | **全部**。`analysis_id` 冻结，任何组件不得假设它可重算 | `DESIGN_RECOMMENDATION` |
| 2 | 哪些需要支持 Result ID？ | Linkage（可选指向）、Review/Impact（必须区分"哪次执行"）、Analysis Index（必须）、Candidate（后续） | `DESIGN_RECOMMENDATION` |
| 3 | 哪些需要验证 Parser Build？ | 写入守卫、Reanalysis 工具、Impact/Review、Seed Policy（未来） | `DESIGN_RECOMMENDATION` |
| 4 | 哪些必须拒绝 UNKNOWN Build？ | **正式路径写入**（G1–G9）、任何"作为 Current 使用"的路径 | `DESIGN_RECOMMENDATION` |
| 5 | 是否需要统一 Identity Resolver？ | **需要**（M.4），否则每个消费者各写一套映射 | `DESIGN_RECOMMENDATION` |
| 6 | 是否存在跨 Build 读取隐患？ | **存在**：Linkage 只钉文件字节，不钉 build → 旧 Linkage 可读到"新 build 写的同路径记录"（今天因 ID 变化不会发生，但守卫缺失时会发生） | `EVIDENCE_CONFIRMED`（无 build 门禁）+ `DESIGN_RECOMMENDATION`（修复方向） |

---

## L. Stage J — Identity Validation & Adversarial Test Design

> 本阶段**只设计**，不新增/修改任何测试代码。

### L.1 Unit Test Design（确定性）

| ID | 用例 | 期望 |
|---|---|---|
| U1 | 同源码同配置两次计算 build identity | 完全一致 |
| U2 | manifest 文件顺序打乱 | 身份不变 |
| U3 | 路径写法 `./a/../a/x.py` vs `a/x.py` | 规范化后一致 |
| U4 | Windows `\` vs `/` | 规范化后一致 |
| U5 | 空闭包/缺文件 | `UNKNOWN`，不抛异常、不静默降级 |
| U6 | 同输入 canonical JSON 在不同换行环境 | `content_sha256` 一致；`file_sha256` 可不同（G8） |

### L.2 Integration Test Design（变更检测）

| ID | 变更 | 期望 |
|---|---|---|
| I1 | 改 Parser 一字节 | build identity 变；`workspace_state=DIRTY_TRACKED` |
| I2 | 改 Adapter | adapter identity 变；parser identity 不变 |
| I3 | 改 `paths.py`（依赖） | parser build identity 变（当前实现在此处**会漏检**，是回归用例） |
| I4 | 新增闭包内未跟踪文件 | 身份变 + `DIRTY_UNTRACKED_RELEVANT` |
| I5 | 忽略文件中的相关源码改变 | 不计入 → `IGNORED_RELEVANT` 告警，不静默通过 |
| I6 | 写正式路径但 build `UNKNOWN` | 拒绝写入 |

### L.3 Historical Compatibility Test Design

| ID | 用例 | 期望 |
|---|---|---|
| H1 | 34 条旧 ID 解析 | 全部可解析，`identity_status=NOT_AVAILABLE` |
| H2 | 150 条 Linkage 引用 | 0 悬挂、`linkage_id` 150/150 可复算 |
| H3 | 尝试"回填" 1.71 build | 必须被拒绝（无来源） |
| H4 | 新旧结果并存 | 旧结果字节不变、旧 Linkage 仍 FRESH |
| H5 | 旁挂 identity 迁移可复算 | M1 产物复算一致；删除可回滚 |
| H6 | 索引新增字段 | 34 条 ID 集合不变 |

### L.4 Adversarial Test Design（写入与碰撞）

| ID | 攻击 | 期望 |
|---|---|---|
| A1 | 同 `analysis_id` 写不同内容 | `REJECT_CONFLICT`，旧文件字节不变 |
| A2 | 同身份同输出重复写 | `REUSE_IDENTICAL`，不产生第二文件 |
| A3 | 同 content、不同 build、不同输出 | `CREATE_NEW_RESULT`，旧结果保留 |
| A4 | 同 content、同 build、不同输出（非确定性） | `CONFLICT_REVIEW`/`QUARANTINE`（**不得**当新结果） |
| A5 | `UNKNOWN` 身份写正式路径 | 拒绝 |
| A6 | 写入过程被中断（模拟 `os.replace` 前崩溃） | 无半成品可见；`.tmp` 残留被识别 |
| A7 | 伪造 `parser_build_identity` 字段 | G3 复算不一致 → 拒绝 |
| A8 | 文件名 ID 与记录 ID 不一致 | G2 拒绝 |
| A9 | 授权替换无凭据 | 拒绝；有凭据 → 审计完整 |
| A10 | 旧目录写入 | `HISTORICAL_READ_ONLY` |
| A11 | 同 `record_id` 两文件 | `DUPLICATE_RECORD_ID` 全拒 |
| A12 | 破坏目标 JSON 后写入 | `QUARANTINE`，不静默重写 |

**四类必须分开统计**：Unit / Integration / Historical / Adversarial，报告中不得混算通过率。

---

## M. Stage K — Identity Implementation Blueprint

### M.1 K1 — Target Data Model

见 E.3 表（字段、类型、必填、缺失值语义）。补充类型约定：

- 所有 digest 为 64 hex 小写；identity 为 `"<prefix>-" + hex`。
- `null` 表示"不适用"；`""` 表示"应存在但缺失"；**两者不得互换**。
- 枚举一律大写 snake，未知值使用 `UNKNOWN`，禁止自由文本。

### M.2 K2 — Identity Generation API（仅接口设计）

```python
# 只读纯函数，全部返回 dataclass/dict，不写盘
compute_source_identity(*, repository, commit, commit_status, source_path,
                        source_bytes_or_none) -> dict
compute_input_identity(*, reference_path, normalization="bytes-v1") -> dict
compute_component_build_identity(*, component, source_files, dependencies,
                                 declared_version, runtime_fingerprint,
                                 workspace_state) -> dict
compute_parser_build_identity(...) -> dict      # component="gd_parse"
compute_adapter_build_identity(...) -> dict     # component="external_code_understanding"
compute_analysis_content_identity(source_identity, input_identity) -> str
compute_analysis_execution_identity(content_identity, parser_build, parser_contract,
                                    adapter_build, adapter_contract, schema_identity,
                                    runtime_fingerprint) -> str
compute_analysis_output_identity(record, *, volatile_keys) -> str
compute_record_id(execution_identity, execution_seq) -> str
validate_identity_manifest(manifest, *, project_root) -> dict   # {ok, errors, recomputed}
```

约束：所有函数必须**幂等、无副作用、不读 env**（除非纳入 `runtime_fingerprint`）。

### M.3 K3 — Write Guard API（仅接口设计）

```python
validate_record_identity(record, *, expected_ids) -> list[str]      # errors
validate_build_identity(record, *, runtime_build) -> list[str]
check_existing_record(target_path, record) -> dict                  # {exists, file_sha256, record_id}
classify_write_operation(existing, incoming) -> str                 # 六类之一
validate_output_conflict(existing, incoming) -> dict                # {conflict, reason}
require_replacement_authorization(auth) -> None                     # 无凭据抛错
atomic_write_record(record, target_path, *, newline="\n") -> str    # 临时文件 + 复读校验 + os.replace
```

`atomic_write_record` **必须**参照 `write_linkage()` 的既有范式（validate → mkstemp → 复读 → replace → 失败 unlink），且显式 `newline="\n"`。

### M.4 K4 — Identity Resolver

```python
resolve_identity(legacy_analysis_id) -> {
    "analysis_id", "record_ids", "identity_status",
    "canonical_analysis_id" | None, "current_record_id" | None,
    "supersedes_chain", "warnings"
}
resolve_record(record_id) -> {"path", "file_sha256", "build_identity", "status"}
```

规则：解析失败**绝不**猜测；34 条旧 ID 必须返回 `identity_status=NOT_AVAILABLE` 与 `current_record_id=<legacy record 自身>`。

### M.5 K5 — Migration Sequence

| 步 | 前置 | 输入 | 输出 | 验证 | 回滚 |
|---|---|---|---|---|---|
| S1 | 本报告验收 | 34 条记录字节快照 | 旁挂 `legacy_identity.json` | 34/34 content/output identity 复算 | 删旁挂 |
| S2 | S1 | 索引 + 旁挂 | 索引新增 `identity_status` | 记录集合/受保护哈希不变 | 恢复索引字节 |
| S3 | S2 | 代码 | `compute_*` 纯函数 + 单测 | U1–U6 | 删除模块 |
| S4 | S3 | 代码 | `validate_*`/`classify_*` + 原子写 | A1–A12（隔离目录） | 删除模块 |
| S5 | S4 | 代码 | 记录写入接入守卫（默认拒覆盖） | `test_batch_b` 幂等断言仍通过 | 关闭开关 |
| S6 | S5 | 3 条样本 | 隔离 Pilot 新结果 | 旧哈希不变 + 新旧并存 | 删隔离目录 |
| S7 | S6 授权 | 34 条 | 正式新结果（未授权前禁止） | 全量清单 + Linkage FRESH | 删新结果目录 |

**任何一步都不得合并到同一次实施。**

### M.6 K6 — Rollout Order（严格串行）

1. Identity Contract（字段 + 常量 + `identity_version=2`）
2. Build Manifest（闭包定义 + 生成 + 校验）
3. Write Guard（G1–G9 + 原子写）
4. Legacy Compatibility（旁挂 + Resolver + 索引字段）
5. Immutable Result Model（`record_id` + 状态机 + Current 选择）
6. Identity Validation（U/I/H/A 全套）
7. Limited Pilot（3 条，隔离）
8. Controlled Reanalysis（34 条，单独授权）

禁止 1–8 任两步合并为一个"大改"。

---

## N. Migration & Rollout Plan（配套）

| 阶段 | 允许写 | 禁止写 | 门禁 |
|---|---|---|---|
| 现在（1.78 后） | 仅设计与测试代码（若被授权） | 正式记录、Linkage、Candidate、Seed | 8 清单哈希不变 |
| 守卫落地后 | 隔离工作区 | 旧目录 | G5/G9 |
| Pilot | 隔离工作区新结果 | 正式目录 | 3 条样本 + 人工验收 |
| 正式重跑 | 新结果目录（`records/v2/`） | 旧目录任何字节 | 单独授权 + 全量哈希 |

**回滚原则**：每一步产物独立可删；旧记录永不作为回滚对象（因为从不被改）。

---

## O. Risk Register

| ID | 风险 | 影响 | 概率 | 现有缓解 | 需新增 |
|---|---|---|---|---|---|
| R-01 | 就地补字段导致 150 条 Linkage 全 STALE | 高 | 若按"简单方案"实施 → 必然 | 本报告禁止就地迁移 | 旁挂 + G5 |
| R-02 | ID 与版本耦合（历史）；新契约下若继续耦合 build | 高 | 中 | 本设计拆 content/execution | 实施解耦 |
| R-03 | `analysis_record_digest` 跨平台漂移（CRLF/LF） | 中 | **已发生**（34 CRLF vs 150 LF） | 无 | G8 双摘要 |
| R-04 | 无 build 字段 → 无法证明"同 ID 同输出" | 高 | 已存在 | 只读使用 + 限制标注 | 新记录强制 build |
| R-05 | 守卫默认拒绝覆盖会破坏既有幂等测试 | 中 | 确定（N-4） | 无 | `REUSE_IDENTICAL` |
| R-06 | 闭包漏 `paths.py` 等依赖 | 中 | 已存在（N-6） | 无 | 显式依赖清单 |
| R-07 | 34 条无法回填 build → 永远 `NOT_AVAILABLE` | 中 | 确定 | 只读 | 接受限制并在下游显示 |
| R-08 | Seed Policy 无身份门禁 | 中 | 确定 | 靠 digest 链隐式阻止 | 未来显式门禁 |
| R-09 | Dirty workspace 写入正式路径 | 高 | 当前即 DIRTY_TRACKED | 无 | G9 |
| R-10 | 半成品写入（无原子写） | 中 | 已存在 | 无 | G7 |
| R-11 | 授权替换被滥用/无审计 | 高 | 低 | 无 | G6 凭据 + 审计 |
| R-12 | 字段膨胀导致哈希自引用/循环 | 中 | 中 | 无 | E.3 明确 Hash Input 列 |
| R-13 | 跨平台路径大小写歧义（Windows） | 低 | 中 | 无 | `OPEN_QUESTION` |

---

## P. Open Questions

| # | 问题 | 本阶段立场 |
|---|---|---|
| Q1 | `analysis_id` 是否最终改为 `canonical_analysis_id`？ | 建议**永不重算**旧值；新对象用新 ID，旧 ID 由 Resolver 映射。是否最终废弃旧 ID 格式 → `OPEN_QUESTION` |
| Q2 | 授权替换凭据采用什么载体（签名文件 / 环境变量 / 人工 PR）？ | `OPEN_QUESTION`；不建议放进记录正文 |
| Q3 | Windows 路径大小写不敏感是否接受？ | `OPEN_QUESTION`；建议 manifest 存原样 + 比较时 `casefold` 并记录警告 |
| Q4 | 新结果目录命名（`records/v2/<analysis_id>/<record_id>.json`）是否作为定案？ | `DESIGN_RECOMMENDATION`，待验收 |
| Q5 | 34 条重跑后，150 条 Linkage 是否升级指向新结果？ | `OPEN_QUESTION`；本阶段建议**不升级**，只新增旁挂指针 |
| Q6 | Seed Policy 的 build/coverage 门禁字段形态？ | `OPEN_QUESTION`；需与 Phase 1.74-C 政策重新评审 |
| Q7 | `runtime_fingerprint` 是否纳入 `analysis_execution_identity`？ | 建议纳入（本设计如此），因跨 Python 版本可能影响 regex 行为；代价是升级 Python 会产生新 execution 身份 |
| Q8 | 输出摘要是否包含 `provenance` 子对象？ | 建议**排除**（provenance 属溯源，不属输出），否则重新核对 provenance 会误判输出变化 |

---

## Q. Final Recommendation（任务书 13 问，逐条标注）

| # | 问题 | 结论 | 标注 |
|---|---|---|---|
| 1 | 推荐哪种 Identity Architecture？ | **C 分层 + B 结果模型**（content/execution/output 三层哈希 + result 状态机） | `DESIGN_RECOMMENDATION` |
| 2 | Analysis ID 是否保留旧值？ | **保留，且永不重算**（34 条原样；新对象用新 ID） | `EVIDENCE_CONFIRMED`（旧 ID 可复算于 1.71）+ `DESIGN_RECOMMENDATION`（冻结策略） |
| 3 | 是否引入独立 Result ID？ | **是**（`record_id`，由 execution identity 派生） | `DESIGN_RECOMMENDATION` |
| 4 | 是否引入 Parser Build Identity？ | **是**，运行时从源码闭包字节计算并写入每条新记录；缺失写 `UNKNOWN`/`NOT_AVAILABLE` | `DESIGN_RECOMMENDATION` |
| 5 | Adapter 是否需要独立 Build Identity？ | **是**，与 Parser 分离（Batch E 证明可独立变化） | `EVIDENCE_CONFIRMED`（职责分离）+ `DESIGN_RECOMMENDATION`（字段） |
| 6 | Build Manifest 必须包含哪些文件/依赖？ | Parser：`gd_parse.py`（+ 递归本项目 import）；Adapter：`external_code_understanding.py`、`source_analysis.py`、`provenance.py`、`paths.py`；排除 `__pycache__`/tests/tmp/文档 | `EVIDENCE_CONFIRMED`（闭包与漏检 N-6）+ `DESIGN_RECOMMENDATION`（清单） |
| 7 | `write_record` 必须有哪些保护？ | G1 存在性、G2 身份一致、G3 build 一致、G4 输出冲突、G5 历史只读、G6 授权替换、G7 原子写、G8 规范化序列化、G9 scope | `DESIGN_RECOMMENDATION` |
| 8 | 如何保护 150 条 Linkage？ | **旧记录字节零改动 + 旁挂身份 + 新结果新目录 + Resolver**；禁止重建/替换 | `EVIDENCE_CONFIRMED`（字节钉死）+ `DESIGN_RECOMMENDATION`（方案） |
| 9 | 如何处理 34 条历史 Analysis？ | 只读保留，`identity_status=NOT_AVAILABLE`，`identity_version=1`；不补字段、不改 ID；未来重跑需单独授权 | `EVIDENCE_CONFIRMED`（34/34 无 build、无 coverage）+ `DESIGN_RECOMMENDATION` |
| 10 | 如何表达历史 UNKNOWN Build？ | 四态 `VERIFIED`/`LEGACY_UNVERIFIED`/`NOT_AVAILABLE`/`UNKNOWN`；**禁止**由版本号反推 | `DESIGN_RECOMMENDATION` |
| 11 | 是否允许开展 Limited Pilot？ | **现在不允许**；需先完成 S3–S5（纯函数 + 守卫 + 原子写），且仅 3 条、仅隔离目录、需人工验收 | `DESIGN_RECOMMENDATION` |
| 12 | 哪些问题仍需独立设计？ | 授权替换凭据（Q2）、Linkage 升级策略（Q5）、Seed 门禁（Q6）、输出摘要边界（Q8）、跨平台路径（Q13/Q3）、Identity Resolver 的缓存与一致性 | `OPEN_QUESTION` |
| 13 | 下一阶段最合理任务？ | **Identity Contract 最小落地设计评审 → 实施 S3（纯函数）**：只写新模块与单测，不碰任何正式数据 | `DESIGN_RECOMMENDATION` |

**不得**把以上任何 `DESIGN_RECOMMENDATION` 描述为已实现能力。

---

## R. Phase Readiness

| 判定 | 值 |
|---|---|
| **Verdict** | **`PASS_WITH_LIMITATIONS`** |
| **Readiness** | **`READY_FOR_IDENTITY_IMPLEMENTATION`** |

限制（全部为设计条件或不可逆历史事实）：

1. 全部字段/守卫/Resolver 为设计，未实现；落地后行为 `NOT_VERIFIED`。
2. 34 条 1.71 Build Identity **不可重建**，只能 `NOT_AVAILABLE`。
3. 150 条 Linkage 的 `analysis_record_digest` 受 CRLF 影响，**无法回溯统一为 LF 摘要**；只能双摘要并存（旧摘要留作历史）。
4. "同 build 同输入不同输出"（A4）无正式数据样本，只能合成测试（N-9）。
5. 授权替换的治理模型（Q2）未定，实施前必须补齐。
6. 本阶段未运行任何测试套件（无需修改代码，且禁止重跑）；Batch E 的 4 套件结果仍是最后一次已知基线。

**Stop Conditions 核对（任务书 17 节）：**

| # | 条件 | 状态 |
|---|---|---|
| 1 | Git 状态无法可靠确认 | **未触发**：已在 B.1 用三种口径对齐 |
| 2 | 1.77 报告与源码重大差异 | **未触发**：11 条结论全部复核成立；仅发现 1.77 的 porcelain 行数口径不完整（B.2），不影响结论 |
| 3 | 无法复算历史 Analysis ID | **未触发**：1.71 下 34/34 |
| 4 | 历史 Linkage 已存在失效引用 | **未触发**：悬挂 0、`linkage_id` 150/150 |
| 5 | 无法确定 `write_record` 全部调用方 | **未触发**：仅 main + 1 测试 |
| 6 | Build Manifest 无法覆盖关键运行依赖 | **已确认存在缺口**（N-6 `paths.py`），但**本阶段只需设计覆盖方案**，不属"无法覆盖"；已在 F.1/F.2 给出闭包清单 |
| 7 | 需修改正式数据才能继续验证 | **未触发** |
| 8 | 操作可能覆盖用户已有文件 | **未触发**：全部实验在内存或临时目录 |
| 9 | 历史记录来源或 Digest 无法确认 | **部分**：34 条记录自身 digest 可复算；但其 **Parser Build** 无法确认 → 已按 `NOT_AVAILABLE` 处理，未推测 |

---

## S. Integrity Evidence

| 检查 | 方式 | 结果 |
|---|---|---|
| Git 基线 | `rev-parse` + `status --porcelain` + `diff --name-only` | `master @ d64b1cd5…`；staged 0、deleted 0；porcelain 180（35 ` M` + 145 `??`）；真实内容差异 31；stat-only 4 |
| 34 条 ID 复算 | 内存 `sha256(repo|commit|path|input_digest|gd_parse|version)[:16]` | 1.71: **34/34**；1.75: **0/34**；1.76: **0/34** |
| `input_digest` 与 Reference 字节 | 重算 sha256 | **34/34** 一致 |
| 34 条字段存在性 | 逐条统计 | `source_digest`/`input_digest` 34/34；`parser_build_identity`、6 个 coverage 字段 **0/34** |
| 34 条 5 元组唯一性 | 分组 | **34/34 唯一、0 重复** |
| 34 条输出摘要唯一性 | canonical digest | **34/34 唯一、0 并列** |
| 序列化可行性 | `dumps(sort_keys,indent=2)` + 换行 | LF: 0/34；**CRLF: 34/34** |
| Linkage 身份 | 复算 `linkage_id` | **150/150** |
| Linkage 外键 | `analysis_id ∈ 记录集合` | **150/150 有效，悬挂 0** |
| Linkage 序列化 | canonical 重建 | **150/150（LF）** |
| Linkage 覆盖 Feature | 统计 | 5 个：`health`、`health_bar`、`blackboard`、`openable_door`、`attack_emitter` |
| 索引一致性 | `index.json` vs 记录集合 | **34/34 一致**，无缺无多；索引条目不含 `parser_version`/build |
| Build Identity（当前） | `corpus_audit_176.parser_build_identity()` | `gd_parse@1.75+build:3b36069a44beb55c`；`gd_parse=f56aa340…`；`adapter=fa30686a…` |
| Build Identity（Batch B） | `parser_1.76/manifest.json` | `gd_parse@1.75+build:6b74a6cd20a06033`（≠ 当前） |
| 写覆盖行为 | 隔离临时目录 | 同 ID 两次写入 → 同路径、1 文件、内容被覆盖 |
| Parser 闭包 | import 扫描 | `gd_parse.py`（无本项目依赖）；`source_analysis.py` → `gd_parse`、`paths`；`provenance.py`（仅标准库）；Adapter 无 env 读取 |
| 受保护数据 | 8 清单 SHA-256（Batch E 方案） | 与本阶段开始前 **8/8 IDENTICAL** |
| 阶段内受保护写入 | 清单哈希 + 字节比对 | **0** |
| 测试 | 本阶段未运行（禁止重跑 / 无需改码） | 未运行（不声称通过） |

---

## T. Git State

```text
Branch  master
HEAD    d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84
Staged  0
Deleted 0
Modified（内容差异）  31（既有，本阶段未新增）
Modified（stat-only） 4（既有，无内容差异）
Untracked 145 行 / 593 文件（既有）→ 本报告写出后 146 行 / 594 文件
本阶段新增文件（唯一）：.ai/context/PHASE_1_78_IDENTITY_CONTRACT_WRITE_PROTECTION_DESIGN.md
```

本阶段未执行任何 Git 写操作；`HEAD` 与本阶段开始时一致。

临时探测文件（位于 gitignored 的 `.ai/tmp/`，阶段结束已删除）：

- `phase178_probe.py`（Git 口径、ID 复算、身份模拟、Linkage、索引、Build Identity、写冲突模拟、受保护清单）
- `phase178_probe2.py`（序列化可行性、依赖闭包、env 扫描、5 元组唯一性）
- `phase178_probe3.py`（CRLF/LF 判定与摘要漂移）

Batch E 遗留的 `batch_e_*.py` / `batch_e_*.json` 属上一阶段产物，本阶段未修改、未删除。

---

## 验收对照

| AC | 要求 | 结果 | 位置 |
|---|---|---|---|
| AC-01 | Identity Domain Separation | 通过（Source/Input/Parser/Adapter/Schema/Content/Output 七层职责与哈希归属明确） | D 节 |
| AC-02 | Deterministic Build Identity | 通过（闭包 manifest + 规范化 + 复算校验 + 三态） | F 节 |
| AC-03 | Legacy Compatibility | 通过（`analysis_id` 冻结 + `legacy_analysis_id` + Resolver） | G.1、M.4 |
| AC-04 | Linkage Preservation | 通过（零字节改动 + 旁挂 + 新目录；禁止重建） | G.2 |
| AC-05 | Write Protection | 通过（G1–G9 + 操作分类 + 决策矩阵 + 原子写） | H 节 |
| AC-06 | Immutable Results | 通过（`record_id` + `supersedes` + 六态状态机 + 非时间戳选择） | I 节 |
| AC-07 | Historical Unknown Handling | 通过（四态 + 禁止反推） | G.3 |
| AC-08 | Reanalysis Decision Contract | 通过（9 类变化 + 8 个具体情形） | J 节 |
| AC-09 | Downstream Compatibility | 通过（9 个消费者实测依赖 + 矩阵 + 6 问） | K 节 |
| AC-10 | Adversarial Test Design | 通过（U/I/H/A 四类，共 30 例） | L 节 |
| AC-11 | Implementation Blueprint | 通过（K1–K6 + 接口 + 迁移序列 + 逐步 rollout） | M 节 |
| AC-12 | Read-only Integrity | 通过（8/8 清单一致、0 写入、Git 无写） | B.3、S、T |
| AC-13 | No Premature Implementation | 通过（未改代码/Schema/数据/测试） | 全文 |

**阶段结束，等待人工验收。未修改 Parser/Adapter/`write_record`/Schema/`PARSER_VERSION`/`_analysis_id`；未重跑 Analysis 或 Batch B；未创建 Analysis ID；未改 Linkage/Candidate/Seed；未执行 Pilot；未执行 Git 写；未进入下一阶段。**
