#!/usr/bin/env python3
"""Asset Registry 测试夹具 —— 在临时目录构造一个真实可扫描的 Godot 资源树。

只写标准资源文件（PNG / WAV / .tres），不依赖 Pillow、不依赖 Godot；
asset_registry 的工具（scan / index / query / bind / check）都可以直接在上面运行。

生成的结构（约定：Assets/<类别>/<主体>/<动作>/<帧>）：

    Assets/
    ├── characters/
    │   ├── player/{idle,run,attack,hurt}/player_<动作>_00.png ...
    │   │   └── player_frames.tres          (SpriteFrames: idle/run/attack/hurt)
    │   └── enemy/slime/{idle,move,attack,hurt}/slime_<动作>_00.png ...
    │       ├── slime_frames.tres           (SpriteFrames: idle/move/attack/hurt)
    │       └── death/slime_death_00.png    (只在磁盘，未进 SpriteFrames)
    ├── environment/tiles/ground.png + environment/tilesets/ground_tileset.tres
    ├── ui/icons/health_icon.png
    └── audio/slime/{hurt,attack}.wav
"""

from __future__ import annotations

import math
import os
import struct
import zlib
from pathlib import Path

# 每个动作目录的帧模板（颜色各不相同，便于人工辨认；内容不参与分类）
FRAME_COLOR = {
    "idle": (90, 170, 255, 255),
    "move": (90, 255, 150, 255),
    "attack": (255, 120, 90, 255),
    "run": (200, 170, 255, 255),
    "hurt": (255, 220, 90, 255),
    "hurt_sfx": (255, 255, 255, 255),
}

# 动作 -> 帧数。hurt 既在 SpriteFrames 里（动画）也作为独立音频存在，
# 用于验证「同名角色不同资源类型」的 disambiguation 与 *_sfx 角色绑定。
PLAYER_ACTIONS = {"idle": 2, "run": 2, "attack": 1, "hurt": 1}
SLIME_ACTIONS = {"idle": 2, "move": 3, "attack": 2, "hurt": 1}
# death 只有帧、不进 SpriteFrames：用于验证「无 SpriteFrames 时退化为首帧静态贴图」
SLIME_EXTRA_ACTIONS = {"death": 1}


def write_png(path: Path, width: int = 32, height: int = 32,
              color: tuple = (255, 255, 255, 255)) -> Path:
    """写一个合法的 RGBA PNG（纯标准库）。"""
    raw = b"".join(b"\x00" + bytes(color) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return path


def write_wav(path: Path, seconds: float = 0.25, rate: int = 8000,
              freq: float = 440.0) -> Path:
    """写一个合法的 16-bit 单声道 PCM WAV（纯标准库）。"""
    total = int(rate * seconds)
    frames = b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / rate)))
                      for i in range(total))
    header = (b"RIFF" + struct.pack("<I", 36 + len(frames)) + b"WAVE"
              + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
              + b"data" + struct.pack("<I", len(frames)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + frames)
    return path


def write_spriteframes_tres(path: Path, animations: dict) -> Path:
    """写 SpriteFrames（.tres），animations = {动画名: [res:// 帧路径, ...]}。"""
    lines = []
    resources = []
    animation_blocks = []
    index = 0
    for name, frames in animations.items():
        entries = []
        for frame in frames:
            index += 1
            res_id = "%d_%s" % (index, name)
            resources.append('[ext_resource type="Texture2D" path="%s" id="%s"]'
                             % (frame, res_id))
            entries.append('"duration": 1.0,\n"texture": ExtResource("%s")' % res_id)
        animation_blocks.append(
            '{\n"frames": [{\n%s\n}],\n"loop": true,\n"name": &"%s",\n"speed": 6.0\n}'
            % ("}, {\n".join(entries), name))

    lines.append('[gd_resource type="SpriteFrames" load_steps=%d format=3]' % (len(resources) + 1))
    lines.append("")
    lines.extend(resources)
    lines.append("")
    lines.append("[resource]")
    lines.append("animations = [%s]" % ", ".join(animation_blocks))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def write_tileset_tres(path: Path, texture_res: str, tile_size: int = 16,
                       columns: int = 2, rows: int = 2) -> Path:
    """写 TileSet（.tres），带一个 TileSetAtlasSource 图块源。"""
    lines = [
        '[gd_resource type="TileSet" load_steps=3 format=3]',
        "",
        '[ext_resource type="Texture2D" path="%s" id="1_ground"]' % texture_res,
        "",
        '[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_ground"]',
        "texture = ExtResource(\"1_ground\")",
        "texture_region_size = Vector2i(%d, %d)" % (tile_size, tile_size),
    ]
    for row in range(rows):
        for column in range(columns):
            lines.append("%d:%d/0 = 0" % (column, row))
    lines += [
        "",
        "[resource]",
        "tile_size = Vector2i(%d, %d)" % (tile_size, tile_size),
        'sources/0 = SubResource("TileSetAtlasSource_ground")',
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def build_assets(root: Path) -> dict:
    """在 root 下写出完整资源树，返回 {res_path: disk_path}。"""
    root = Path(root)
    files: dict[str, Path] = {}

    def track(path: Path) -> Path:
        rel = path.relative_to(root).as_posix()
        files["res://" + rel] = path
        return path

    # 角色：player / slime 的动作帧
    # 主体目录：player -> characters/player（玩家只有一个）；slime -> characters/enemy/slime
    characters = (("player", PLAYER_ACTIONS, (), "characters/player"),
                  ("slime", SLIME_ACTIONS, tuple(SLIME_EXTRA_ACTIONS), "characters/enemy/slime"))
    for subject, actions, extras, relative in characters:
        base = root / "Assets" / relative.replace("/", os.sep)
        frame_paths = {}
        for action, count in actions.items():
            frames = []
            for index in range(count):
                frame = base / action / ("%s_%s_%02d.png" % (subject, action, index))
                write_png(frame, 32, 32, FRAME_COLOR[action])
                track(frame)
                frames.append("res://" + frame.relative_to(root).as_posix())
            frame_paths[action] = frames
        track(write_spriteframes_tres(base / ("%s_frames.tres" % subject), frame_paths))

        # 只有帧、不进 SpriteFrames 的动作（验证无 SpriteFrames 时的退化绑定）
        for action in extras:
            for index in range(SLIME_EXTRA_ACTIONS[action]):
                frame = base / action / ("%s_%s_%02d.png" % (subject, action, index))
                write_png(frame, 32, 32, FRAME_COLOR.get(action, (200, 200, 200, 255)))
                track(frame)

    # 环境：tileset
    ground = track(write_png(root / "Assets" / "environment" / "tiles" / "ground.png",
                             32, 32, (120, 100, 70, 255)))
    track(write_tileset_tres(root / "Assets" / "environment" / "tilesets" / "ground_tileset.tres",
                             "res://" + ground.relative_to(root).as_posix()))

    # UI 图标
    track(write_png(root / "Assets" / "ui" / "icons" / "health_icon.png", 16, 16,
                    (255, 60, 60, 255)))

    # 音频：史莱姆受击 / 攻击
    track(write_wav(root / "Assets" / "audio" / "slime" / "hurt.wav", 0.2, 8000, 300.0))
    track(write_wav(root / "Assets" / "audio" / "slime" / "attack.wav", 0.2, 8000, 600.0))

    return files


def build_project(root: Path, scenes: bool = True) -> Path:
    """构造一个最小可用项目骨架：Assets/ + .ai/context/ + Scenes/。"""
    root = Path(root)
    build_assets(root)
    (root / ".ai" / "context").mkdir(parents=True, exist_ok=True)
    if scenes:
        (root / "Scenes").mkdir(parents=True, exist_ok=True)
    return root


if __name__ == "__main__":  # pragma: no cover - 手工生成真实资源树
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(build_project(target))
