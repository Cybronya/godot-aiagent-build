# sfx_pool — 音效池组件

运行时创建一组 `AudioStreamPlayer` 轮转播放一次性音效（SFX）：枪声、脚步、拾取
提示音等。池化避免频繁实例化，轮转抢占保证最新音效总能响。

## 教学来源

- [KenneyNL/Starter-Kit-3D-Platformer — audio.gd](https://github.com/KenneyNL/Starter-Kit-3D-Platformer)（MIT）：
  12 播放器池 + 队列 + 音调随机（`pitch_scale = randf_range(0.9, 1.1)`）。
  收藏于 `code_library/references/audio/`（蒸馏片段）。

## 抽象取舍

| 参考实现 | 本组件 |
|---|---|
| `play(path: String)` 每次重新 load | `play(stream: AudioStream)`，流由调用方持有（可预加载） |
| `_process` 轮询队列、延迟到下一帧 | `play` 同步取播放器立即播放，并同步广播 `played` |
| 空闲不足时音效排队等待 | **轮转抢占**：池满直接复用下一个播放器，最新音效优先 |
| 无占用统计 | `active_count()` 读自管簿记（headless 下也确定） |

## 关键设计：簿记自管

引擎在 headless / 无音频设备环境下 `playing` 恒为 false 且 `finished` 可能不触发。
本组件**绝不读引擎播放状态**：play 标记占用、finished 归还、重复 finished 幂等——
行为证据与运行环境解耦。

## 用法

```gdscript
# 实例化为场景节点，触发时：
$SfxPool.play(preload("res://Assets/hit.wav"))
```

音调随机 `pitch_scale ∈ 1±pitch_range`，同一段音效连播不刺耳。

## 验证

```bash
godot --headless --path . -s res://Features/sfx_pool/test_sfx_pool.gd
```
