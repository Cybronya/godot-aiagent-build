# examples/ — Agent 自制示例代码

本目录存放 **Agent 自己编写并验证过**的可复用示例代码。

## 与 code_library/ 的边界

| 目录 | 来源 | 说明 |
|---|---|---|
| `examples/`（本目录） | Agent 制作 | 结合本项目约定写出的教学性示例 |
| `code_library/` | GitHub 下载 | 外部优质代码，含出处与许可证 |

## 存放规则

- 按功能域建子目录（如 `movement/`、`combat/`、`ui/`），与
  `code_library/references/` 的 domain 分类保持一致。
- 每个示例文件头部注释说明：解决什么问题、依赖哪些节点/约定、如何适配。
- 生产代码请放 `Features/` / `Scenes/` 等项目目录，不要放在这里。
