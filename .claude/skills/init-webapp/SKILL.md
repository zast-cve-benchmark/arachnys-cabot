---
name: init-webapp
description: Generate a concise root CLAUDE.md (Stack / Layout / Rules / Auth) for a web application, as context for downstream security-audit agents. Use when asked to "init webapp", "generate webapp CLAUDE.md", or to prime a target codebase before auditing.
---

# Init Webapp

## Task

Generate a `CLAUDE.md` at the root of the target web application. The file is a
compact context primer consumed by later audit agents — it has exactly four
sections: `## Stack`, `## Layout`, `## Rules`, `## Auth`.

You — the main agent — are a **pure scheduler**. You do NOT read source files and
you do NOT write `CLAUDE.md` yourself. All codebase reading and all writes are
done by sub-agents you dispatch. Your job: dispatch sub-agents in the right
order, then run a final check.

## Arguments

- **PROJECT_ROOT** — absolute path to the webapp root. If not provided, use the
  current working directory.

## Precondition

If `<PROJECT_ROOT>/CLAUDE.md` already exists, STOP immediately. Do not overwrite
it — an existing file may be hand-written. Report that the file already exists
and exit.

## Workflow

### Wave 0 — Dispatch webapp-scout

Dispatch ONE `webapp-scout` sub-agent via the `Agent` tool with `subagent_type`
set to `webapp-scout`. Give it PROJECT_ROOT. It detects the
stack and **Write**s the initial `CLAUDE.md` skeleton: a filled `## Stack`
section, a `## Layout` section holding the single placeholder line
`(building tree...)`, a `## Rules` section copied verbatim from the Rules list
below, and a `## Auth` section holding only `(probing...)`.

It returns the **framework name**. Wait for it to finish — every later wave
needs the skeleton to exist.

### Wave 1 — Dispatch layout-builder and auth-probe in parallel

Dispatch, in a single parallel batch, both via the `Agent` tool with
`subagent_type` set to the agent's name:

- ONE `layout-builder` sub-agent (`subagent_type: layout-builder`) — pass it
  PROJECT_ROOT and the framework name,
- ONE `auth-probe` sub-agent (`subagent_type: auth-probe`) — pass it
  PROJECT_ROOT and the framework name.

`layout-builder` walks the whole workspace by directory and file *names* (it
reads no source), replaces the `(building tree...)` placeholder with a single
fenced directory tree, and writes one `- <dir>/ — (explaining...)` line per
directory it judges worth a deeper explanation. `auth-probe` fills `## Auth`.
Their edit anchors differ, so they never collide.

`layout-builder` returns the **list of directories** it marked
`(explaining...)`. Wait for it to finish — Wave 2 depends on that list.

### Wave 2 — Dispatch dir-explainer per nominated directory

For each directory `layout-builder` returned, dispatch one `dir-explainer`
sub-agent via the `Agent` tool with `subagent_type` set to `dir-explainer`. Cap
concurrency at 4 by default; if there are more than 4 directories, dispatch them
in batches of 4. If the user specified a different worker concurrency, honor that
instead.

Pass each `dir-explainer`:

- PROJECT_ROOT,
- the one directory it owns (verbatim, as returned by `layout-builder` — this is
  its exact edit anchor),
- the framework name.

Each sub-agent edits `CLAUDE.md` itself. You do not touch the file. Edits never
collide because every sub-agent targets its own unique placeholder string.

### Final check

Read `<PROJECT_ROOT>/CLAUDE.md`. Verify that all four sections — `## Stack`,
`## Layout`, `## Rules`, `## Auth` — exist and are non-empty, and that no raw
`(building tree...)`, `(explaining...)`, or `(probing...)` placeholder remains. A
`(timeout — manual inspection needed)` note left by a sub-agent is acceptable.

If a raw placeholder is still present, re-dispatch the matching sub-agent for
that one piece. When everything is filled, report the final `CLAUDE.md` path and
stop.

## Rules

The following rules are copied verbatim into the generated `CLAUDE.md`'s
`## Rules` section by the `webapp-scout` sub-agent. Edit this list to add or
change rules; the next `init-webapp` run will reflect the update.

- Do not read any files under `.zast/`. It is the runtime working directory for the audit tool; its logs and intermediate files are not part of the application source and will mislead analysis.
- Do not unzip/extract `.jar`/`.war`/`.zip` archives or decompile `.class` bytecode. Audit source code only — compiled artifacts are not source and carry no usable line numbers. If only compiled artifacts are available for some part of the project, report that source is unavailable for that part rather than attempting to recover it from binaries.
