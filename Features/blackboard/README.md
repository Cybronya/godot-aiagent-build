# blackboard

> 状态：**脚手架**（由 github_collector.py promote 生成，尚未完成抽象）。

## 来源片段

- snippet: `bitbrain__beehave__addons__beehave__blackboard.gd`
- 出处: https://github.com/bitbrain/beehave/blob/godot-4.x/addons/beehave/blackboard.gd
- 仓库: bitbrain/beehave（star 3312）| License: MIT

## 抽象清单（agent 执行）

1. 通读片段（`<name>.gd` 为原始拷贝），理解思路。
2. 按本项目约定重写：剥除具体 NodePath / autoload 依赖；Health 子节点、
   `add_to_group("enemies")`、Orchestration 契约等按需适配。
3. 重写 `<name>.gd` 为正式实现，重写 feature.yaml 的
   summary / provides / interfaces / ownership。
4. 实现 `test_blackboard.gd`（当前是 FAIL 占位，必须替换为真实自测）。
5. 跑 `python .ai/tools/feature_registry/build_feature_index.py` 刷新资产库，
   并用 feature.yaml 里的 validation.command 验证。

片段许可证: MIT（对外发布需遵守，含署名义务）。
