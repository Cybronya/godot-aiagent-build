# Godot Art Assets Skill v3

这是一个面向 Godot 项目的 AI Agent Art Asset 管理 Skill。

v3 将完整的 Skill 规则体系与实际工具整合：

- 规范目录初始化
- 资源扫描
- 新增 / 修改 / 删除检测
- SHA-256 内容识别
- 路径 / 文件名 hints
- 人工语义确认
- Manifest 管理
- 规范检查
- 安全整理
- Godot 引用保护原则

## 核心原则

Scanner 只收集客观事实，不进行视觉识别，也不把文件名猜测直接当成最终语义。

AI Agent 可以根据路径、文件名、规则和 manifest 自动工作；不确定的资源进入 pending / review。

## 快速开始

在 Godot 项目根目录解压本包，然后：

```bash
python .ai/tools/godot-art-assets/scan_assets.py init
python .ai/tools/godot-art-assets/scan_assets.py sync
python .ai/tools/godot-art-assets/scan_assets.py check
```

如果需要人工确认：

```bash
python .ai/tools/godot-art-assets/scan_assets.py review
```

编辑 `.ai/context/asset_reviews/*.review.json` 中的 `asset.human`，然后：

```bash
python .ai/tools/godot-art-assets/scan_assets.py apply
```

## 依赖

Python 3.9+。

可选安装 Pillow 以读取 PNG/JPEG/WebP 等图片尺寸：

```bash
pip install pillow
```

没有 Pillow 时，尺寸字段可能为 `null`，其余扫描功能仍可使用。

## 项目中的核心文件

```text
.ai/
├── skills/godot-art-assets/       # Agent 规则
├── tools/godot-art-assets/        # 执行工具
└── context/
    ├── asset_manifest.json        # 项目资产索引
    └── asset_reviews/             # 人工确认表
```

`PACKAGE_STRUCTURE.md` 是本发行包的说明文档，正式项目中可以删除。
