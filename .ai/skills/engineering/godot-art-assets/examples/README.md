# Examples

## Example 1: new character frame

```text
assets/characters/enemies/goblin/goblin_attack_00.png
```

Hints may include:

```json
{
  "path_hints": ["character", "enemy"],
  "filename_hints": {
    "actions": ["attack"],
    "directions": []
  }
}
```

These remain hints until semantic metadata is confirmed.

## Example 2: uncertain file

```text
assets/mystery_01.png
```

Do not guess. Put it in pending/review.
