# Architecture Decision Lifecycle

```text
proposed → accepted → superseded
```

Other terminal states:

```text
proposed → rejected
accepted → deprecated
```

## Accepted

An active architectural constraint.

## Superseded

A later accepted decision replaces it. Preserve historical records.

## Change Process

1. Identify the old decision.
2. Explain why it no longer fits.
3. Create a replacement.
4. Link the replacement with `supersedes`.
5. Mark the old decision `superseded`.
6. Update architecture overview and index.

Never silently change the meaning of an accepted decision.
