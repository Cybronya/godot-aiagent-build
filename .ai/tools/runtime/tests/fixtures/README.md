# Runtime Playtest Fixtures

每个子目录都是一个**最小、独立、可运行的 Godot 项目**（含自己的 `project.godot`），
用于制造确定性的运行期错误。它们只服务于 Runtime Playtest / Self-Repair 测试。

规则：

- 测试运行时把 fixture 复制到临时目录再执行，**永不就地修改**；
  因此带修复的用例可以重复运行。
- fixture 内不使用 `class_name`，避免与主项目的脚本类缓存互相影响；
  fixture 位于隐藏目录 `.ai/` 下，Godot 也不会把它当作主项目的资源。
- `.godot/` 缓存不入库（`.gitignore` 已忽略）。

| fixture | 制造的问题 | 期望结果 |
|---|---|---|
| `broken_node_path` | `get_node("Helth")` 拼写错误，场景里真实节点是 `Health` | FAIL / `node_not_found` / 可自动修复（单次尝试 PASS） |
| `multiple_node_paths` | 两处节点路径拼写错误（`Helth` / `Manah`） | FAIL / 需要两次尝试才 PASS（验证 max-attempts 循环） |
| `revert_case` | 修复节点路径后仍会暴露另一个错误（`do_something()` 不存在） | FAIL / 修复被回滚（验证回滚路径） |
| `script_error` | `10 / 0` 触发 `SCRIPT ERROR: Division by zero ...` | FAIL / `script_error` / 不可自动修复 |
| `parser_error` | 调用未定义函数，脚本编译失败 | FAIL / `parser_error` / 不可自动修复 |
| `missing_resource` | 场景引用不存在的 `res://Scenes/DoesNotExist.tscn` | FAIL / `resource_missing` |
| `hangs` | `_ready()` 中的 `while true: pass` 永不返回 | TIMEOUT（同时用于「Scene 不存在 → `scene_load_error`」用例） |

被测的**正常场景**使用真实项目：`res://Scenes/EnemyBasic.tscn`（Test 1 → PASS / exit_code 0）。
