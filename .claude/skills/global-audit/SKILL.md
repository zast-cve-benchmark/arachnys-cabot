---
name: global-audit
description: Top-level orchestrator for global (non-per-endpoint) security audit. Detects which frameworks the project uses, then dispatches global-audit-worker instances concurrently via the Agent tool. Always dispatches 4 foundation workers (global-audit-crypto, global-audit-auth, global-audit-config, global-audit-security-components), plus one global-audit-stack worker per recognized framework.
---

# global-audit

You are the orchestrator for global configuration audit. Follow the 4 phases in strict order.

## Context

The project being audited is rooted at your current working directory (cwd). All Read / Glob / Grep paths in this skill — and in every worker you dispatch — are relative to that cwd. Do not search for "the project" anywhere else.

## Phase 0  Resolve OUTPUT_DIR

- Parse `--output-dir <X>` from user input.
- `OUTPUT_DIR = X` (caller always passes `--output-dir`).
- `mkdir -p $OUTPUT_DIR/vulns/` — this is where workers write.

## Phase 1  Detect frameworks

Identify the web/security frameworks the project uses. Use whatever method gets the answer reliably — read project root files, build configs, source imports — your call.

Output a set of `(language, framework)` pairs, e.g. `{(java, shiro), (java, spring-security)}`.

If detection yields an empty set, Phase 2 still dispatches the 4 foundation workers. Phase 2 framework-specific dispatch is just empty. Never fail on detection.

## Phase 2  Create audit agents

**The subagent type for all workers is `global-audit-worker`** (defined in `agents/global-audit-worker.md`).

1. **Always dispatch 4 foundation workers in parallel** — one each for the 4 foundation sub-skills:
   - `global-audit-crypto`
   - `global-audit-auth`
   - `global-audit-config`
   - `global-audit-security-components`

2. For each `(language, framework)` detected in Phase 1, look up the routing table below. If a match is found, use the `Agent` tool to create one additional worker for `global-audit-stack` with that `LANGUAGE` and `FRAMEWORK`.

3. ALL `Agent` calls in this Phase MUST be emitted in the SAME assistant message so they run concurrently.

### Routing table

| language     | framework                | reference file                                          |
|--------------|--------------------------|---------------------------------------------------------|
| java         | spring-security          | `references/java/spring-security.md`                    |
| java         | shiro                    | `references/java/shiro.md`                              |
| java         | spring-boot-actuator     | `references/java/spring-boot-actuator.md`               |
| python       | django                   | `references/python/django.md`                           |
| python       | flask                    | `references/python/flask.md`                            |
| python       | fastapi                  | `references/python/fastapi.md`                          |
| javascript   | express                  | `references/javascript/express.md`                      |
| javascript   | nestjs                   | `references/javascript/nestjs.md`                       |
| javascript   | koa                      | `references/javascript/koa.md`                          |
| php          | laravel                  | `references/php/laravel.md`                             |
| php          | symfony                  | `references/php/symfony.md`                             |
| php          | wordpress                | `references/php/wordpress.md`                           |
| go           | (any)                    | (skip — go has no framework reference yet)              |
| (other)      | (any)                    | (skip — note it but do not fail)                        |

Paths are relative to `global-audit-stack/`. For unlisted combinations, the framework-specific dispatch is empty (custom or unknown framework safety code is audited by `global-audit-security-components` as the project's own code).

### Agent prompt format

For each foundation worker (4 of them, one per skill — one Agent call per skill):

```
OUTPUT_FILE:   <absolute path>
AUDIT_SKILL:   global-audit-crypto    (or global-audit-auth, global-audit-config, global-audit-security-components)
```

For each stack worker:

```
OUTPUT_FILE:   <absolute path>
AUDIT_SKILL:   global-audit-stack
LANGUAGE:      <language>
FRAMEWORK:     <framework>
```

`OUTPUT_FILE` for each worker must be a unique path under `$OUTPUT_DIR/vulns/`:
- foundation workers → `$OUTPUT_DIR/vulns/global-crypto.json` / `global-auth.json` / `global-config.json` / `global-security-components.json`
- stack worker → `$OUTPUT_DIR/vulns/global-stack-<language>-<framework>.json`

## Phase 3  Validate worker outputs

The Python task reads `$OUTPUT_DIR/vulns/global-*.json` **directly**. You do NOT emit the final JSON — your job in this phase is to verify each worker file passes schema validation, surfacing any worker that skipped its own validation step.

After all workers complete, glob `$OUTPUT_DIR/vulns/global-*.json`. For each matched file `<F>`:

```bash
python .claude/skills/record-vulnerabilities/scripts/validate_vulns.py <F>
```

- **Exit 0** → file is good.
- **Non-zero** → log one line: `Phase 3 reject: <F>: <first stderr line>` and either (a) Edit `<F>` to fix the schema and re-validate, or (b) delete `<F>` so it does not feed into the Python layer. Do not silently leave a broken file in `$OUTPUT_DIR/vulns/`.

Worker output that was sent only in the worker's agent reply (not written to its `<OUTPUT_FILE>`) is invisible to the Python layer — `<OUTPUT_FILE>` is the sole data channel.

## Phase 4  Final report-back

One short message summarizing what you did. Example:

```
Phase 1 detected frameworks: java/shiro, java/spring-boot-actuator.
Phase 2 dispatched 6 workers (4 foundation + 2 global-audit-stack).
Phase 3 validated all 6 worker files (exit 0). 12 candidates total.
```

Do NOT emit a JSON block. The Python task reads the worker files directly and ignores your reply for data extraction.
