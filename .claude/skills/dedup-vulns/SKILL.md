---
name: dedup-vulns
description: Deduplicate ONE batch of already-grouped vulnerability findings. Reads a JSON array of compact findings from --input, judges which findings describe the SAME underlying vulnerability, and replies with the list of finding ids to KEEP. Read-only; never modifies files.
---

# dedup-vulns

You deduplicate ONE batch of vulnerability findings that the caller has already
grouped (they share a category). Your job: decide which findings describe the
**same underlying vulnerability**, and report which finding `id`s to **keep**.

## Context

The project being audited is rooted at your current working directory (cwd). All
Read / Glob / Grep paths are relative to that cwd.

## Phase 0  Read the batch

- Parse `--input <PATH>` from user input. `Read` that JSON file.
- It is a JSON array of findings, each with:
  `id`, `category_id`, `description`, `target`, `locations` (file:line list),
  `exploit_steps`.

## Phase 1  Judge duplicates

Two findings are the **same underlying vulnerability** when they are the same
defect reachable/exploitable the same way — typically same root cause at the same
code location(s), same category, same target. Use judgement, not string equality:
descriptions and data flows are often worded differently for the same bug.

- When unsure whether two findings overlap, `Read`/`Grep` the source at their
  `locations` to confirm before merging them.
- **Bias toward keeping.** Only collapse findings you are confident are the same.
  Different sinks, different endpoints, or different root causes are DIFFERENT —
  keep them all. Losing a real finding is worse than a leftover duplicate.

For each cluster of duplicates, pick exactly one **representative** to keep
(prefer the one with the most complete `locations` / `description`). Every
finding that is NOT a duplicate of another is its own cluster — keep it.

## Phase 2  Reply with the ids to keep

End your reply with a single fenced JSON array of the `id`s to keep — one per
surviving cluster. Use the exact `id` strings from the input. Example:

```json
["aaaa1111", "cccc3333"]
```

Rules:
- The array MUST contain only `id`s that appear in the input.
- You MUST keep at least one id (never reply with an empty array).
- Do not write any files. Your reply text is the only output.
