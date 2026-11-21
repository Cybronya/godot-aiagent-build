# Phase 1.73 — Batch B.2
# Stage E — MizGodotTools Provenance Resolution

Target: `Miziziziz/MizGodotTools`. Batch B.1 rejected it because the mirror records only a
12-character commit and `provenance_status=incomplete`.

## E.1 Final status

**`PROVENANCE_RESOLVED`** — full commit SHA obtained and content-verified:

```
cb548f9035a3b892e34aebbadcb923e68327f2f8
```

## E.2 What the mirror actually held

`code_library/sources/Miziziziz__MizGodotTools/_meta.json`:

```json
{ "full_name": "Miziziziz/MizGodotTools", "branch": "main",
  "commit_sha": "cb548f9035a3", "fetched_at": "2026-10-29",
  "pushed_at": "2026-07-20T18:26:45Z", "gd_file_count": 71,
  "license": "MIT", "license_ok": true }
```

* No `commit_sha_full`, no `.git` directory, no `packed-refs`, no REFL OG, no 40-hex string
  anywhere under the repository's mirror tree (`grep -E '[0-9a-f]{40}'` → no hit).
* `catalog.yaml` repeats the same 12-char value for all 71 entries and stores only 12-char
  `sha256` prefixes.
* Directory layout: `LICENSE`, `README.md`, `_meta.json`, `gd/`.

So the full SHA genuinely could not be recovered from local state.

## E.3 Read-only mechanism used

Two authorised read-only routes were attempted, both with `urllib` against public GitHub
endpoints; **no Git command was run**, no `fetch`/`pull`/`checkout`, nothing was written to the
mirror, catalog or any record.

1. **GitHub REST API** (`api.github.com/repos/.../commits/cb548f9035a3`) — refused with
   `HTTP 403 rate limit exceeded` (unauthenticated quota exhausted; no token in the environment).
   The project's own `github_collector.py` uses exactly this API, so the mechanism is authorised,
   but it was unavailable at audit time.
2. **Public commit endpoints that do not consume API quota** —
   * `https://codeload.github.com/Miziziziz/MizGodotTools/tar.gz/<ref>` — accepted the 12-char
     ref and returned the tree (1,157,972 bytes) whose top directory was named with that same
     short ref, so it confirms resolution but does not reveal the long form.
   * `https://github.com/Miziziziz/MizGodotTools/commit/cb548f9035a3.patch` — returned
     `HTTP 200`, and its first line is the mbox `From` header:

     ```
     From cb548f9035a3b892e34aebbadcb923e68327f2f8 Mon Sep 17 00:00:00 2001
     From: "Miziziziz" <tallnarwal@gmail.com>
     Date: Mon, 20 Jul 2026 14:26:43 -0400
     Subject: [PATCH] Update .gitignore
     ```

     This yields the full 40-character SHA. Re-downloading the tarball at the **full** SHA gave
     top directory `MizGodotTools-cb548f9035a3b892e34aebbadcb923e68327f2f8`, which matches.

## E.4 Identity consistency (all six checks)

| Requirement | Evidence | Result |
|---|---|---|
| Repository identity | `_meta.json.full_name` = `Miziziziz/MizGodotTools`; both endpoints served that repository; catalog `repo` field identical | OK |
| Commit identity | 12-char ref is unique and GitHub resolved it to one commit; `pushed_at 2026-07-20T18:26:45Z` matches the commit's author date `2026-07-20 14:26:43 -0400` | OK |
| Source file ↔ commit | all **71/71** `.gd` files in the mirror are byte-identical to the same paths in the tarball at the full SHA (`match 71, missing 0, diff 0`) | OK |
| Source digest | sha256 of the mirror files equals sha256 of the commit files; spot values `health_manager.gd = 31c603441df044db…`, `damage_data.gd = 461ad21efae64fd2…` also match the catalog's 12-char prefixes | OK |
| Immutable commit URL | `https://github.com/Miziziziz/MizGodotTools/blob/cb548f9035a3b892e34aebbadcb923e68327f2f8/characters_utility/health_manager/health_manager.gd` | constructible |
| Licence | `LICENSE` in the mirror is byte-identical to `LICENSE` in the commit (1,066 bytes); MIT | OK |

Because the whole mirror snapshot equals the whole commit tree, the resolution is not a
per-file coincidence: the analysed content **is** that commit.

## E.5 What was deliberately not done

* The mirror `_meta.json`, `catalog.yaml`, provenance records and analysis records were **not**
  modified. Resolving the SHA in an audit does not retroactively make an existing
  `provenance_status=incomplete` record complete; that would rewrite provenance history.
* No repository was added to the corpus, no file was analysed, no linkage was created, no seed
  was produced.
* Nothing was downloaded to disk; both payloads were read into memory only.

## E.6 Consequence for `attack_emitter`

Resolving the SHA removes the *provenance* blocker, not the *evidence* blocker. Even if this
repository entered the corpus, `attack_emitter` would still have zero direct evidence until its
attack-related files (`characters_utility/...`) are analysed through the normal pipeline and
match Feature identifiers.

For a future batch the admission path is now unblocked and requires three ordinary steps:
record `commit_sha_full = cb548f9035a3b892e34aebbadcb923e68327f2f8` in the mirror metadata via
the normal collector, analyse the chosen files through `external_code_understanding.py`, then
rebuild linkage. Those steps are **not** part of Batch B.2.

## E.7 Verdict

`PROVENANCE_RESOLVED` (full SHA `cb548f9035a3b892e34aebbadcb923e68327f2f8`, content-verified by
71/71 file digests + LICENSE). Batch B.1's rejection remains historically correct; the gap it
identified is now closed at the evidence level and reopening admission is deferred to a future
authorised batch.
