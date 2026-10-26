# Skill Identity

## Skill ID

godot-gdscript

## Skill Name

Godot GDScript

## Version

1.0

## Category

foundation

# Registry Metadata

本章节是本 Skill 的 Canonical Metadata。
Registry 仅索引本 Skill，不重复维护这些字段。

## Load Policy

conditional

## Dependencies

### Required

[]

### Related

[]

## Ownership

负责本 Skill 所定义的 Godot GDScript 能力边界，不负责其他 Skill 的专属实现。

# Description

负责 Godot GDScript 编码规范、脚本结构、类型与可维护性约束。

# Purpose

为 Agent 提供明确、可发现、可验证的 Godot GDScript 能力边界。

# Responsibility

## 负责

- 定义本领域的结构、规则与工作流程。
- 在任务涉及本领域时提供实施与验证依据。

## 不负责

- 不接管其他 Skill 的专属职责。
- 不修改 Framework、Registry 或其他 Skill 的 Canonical Metadata。

# Trigger Conditions

- 用户任务明确涉及 Godot GDScript。
- 其他 Skill 的工作流明确需要本领域能力。
- 需要检查或验证本领域相关修改。

# Input Contract

- 当前任务目标。
- 相关项目 Context。
- 涉及本领域的现有文件、结构或约束。

# Workflow

1. 理解任务目标与当前 Context。
2. 检查相关项目结构与现有实现。
3. 按本 Skill 的责任边界制定或执行修改。
4. 验证修改结果是否符合本 Skill 的约束。
5. 输出结果与验证状态。

# Output Contract

- 清晰说明执行内容。
- 列出关键修改与验证结果。
- 不输出超出本 Skill 责任边界的决策。

# Validation

## Validation Method

检查相关文件、结构、规则和任务结果是否满足本 Skill 的责任边界。

## Success Criteria

- 修改符合本 Skill 的规则。
- 未破坏其他 Skill 的责任边界。
- 验证结果可复现。

## Status Update

报告成功、失败、未完成项及其原因。

# Failure Handling

定义：

- 识别本 Skill 执行中的错误、缺失输入或验证失败。
- 在不越权的前提下采取可逆回退或停止操作。
- 涉及职责边界、核心架构或破坏性变更时请求用户确认。


# Code Library

本 Skill 维护一个外部优质 GDScript 代码库，供 Agent 学习与参考。

## 分类边界

- `examples/` — **Agent 自制**的示例代码（沉淀的可复用写法）。
- `code_library/sources/` — 从 GitHub 下载的原始仓库代码（含 LICENSE、_meta.json）。
- `code_library/references/<domain>/` — 蒸馏后的参考片段，头部注释含出处、
  许可证、commit。**带 `.gdignore`，Godot 不会导入这些脚本。**
- `code_library/catalog.yaml` — 机器可读索引（domain / repo / parse_status 等）。
- `code_library/INDEX.md` — 人读索引与检索规则。**检索时先读 INDEX.md。**

## 收集与更新流程

工具：`tools/github_collector.py`（纯标准库）

```text
search   # GitHub API 按 star 自动发现 (language:gdscript, 许可证白名单过滤)
fetch    # codeload tarball 下载, 抽取 .gd/.gdshader + LICENSE + README
catalog  # 蒸馏到 references/, sha256 去重, 生成 catalog.yaml + INDEX.md
check    # scratch 工程 + godot --headless 批量 parse 检查, 回填 parse_status
reindex  # 从 catalog.yaml 重写 INDEX.md
```

- `GITHUB_TOKEN` 环境变量可选，用于提高搜索 API 速率（10 -> 30 次/分）。
- 只收宽松许可证（MIT/BSD/CC0/Apache 等）；GPL/AGPL/未知许可证的仓库默认跳过。
- 重新收集：`catalog` 会重建 references 与索引；`check` 回填 parse 状态。

## Agent 使用规则

1. 片段是**学习参考**，不是可直接复制的生产代码。
2. 落地前必须按本项目约定适配：片段保留原始 `class_name`，直接复制会产生全局类
   冲突（应改 preload 或改名）；同时注意 Health 子节点约定、
   `add_to_group("enemies")`、Orchestration 契约等。
3. `parse_status: FAIL` = 片段依赖原工程上下文，参考思路为主。
4. 片段许可证信息在头部注释；对外发布需遵守对应许可证（含署名义务）。

## 推荐工作流：片段 → Feature 化

收集片段的价值在于学习，最终沉淀为项目自己的可复用资产：

0. **统一搜索**：`python .ai/tools/feature_registry/search_assets.py --query "关键词"`
   同时检索 Features 资产库与参考片段库（--json 供机器消费）。
1. **检索学习**：任务需要某能力时，先看已有 Feature 是否满足；没有则从
   code_library 找相关片段（读 `INDEX.md`，按 domain / 关键词查 `catalog.yaml`），
   理解其思路。
2. **抽象简化**：剥掉原工程的场景耦合与具体 NodePath，套用本项目约定
   （Health 子节点、`add_to_group("enemies")`、信号命名、Orchestration 契约），
   只保留可复用的核心逻辑。
3. **落成 Feature**：`python tools/github_collector.py promote --snippet <id>
   --name <feature_name>` 生成 `Features/<name>/` 脚手架并自动刷新资产库；
   然后重写实现、补全 feature.yaml、实现真实自测。
   **不要**把片段直接拷进业务代码。
4. **复用登记**：Feature 进入 feature registry（feature_index.json /
   feature_graph.json）后，后续任务经 search_assets.py 优先复用 Feature；
   片段本身只作参考，永不进入运行时。

对应 `AGENT_ONBOARDING.md` Rule 2：已有 Feature 直接复用；没有时先查
code_library 找参考实现，再抽象成新 Feature。片段是教材，Feature 才是资产。

# References

- .ai/config/SKILL_TEMPLATE.md
- .ai/config/skill-schema.yaml
- code_library/INDEX.md
- tools/github_collector.py


# Examples

当任务涉及 Godot GDScript 时，先读取本 Skill，再根据 Workflow 执行与验证。
