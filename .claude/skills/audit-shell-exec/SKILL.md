---
name: audit-shell-exec
description: Audit endpoints with shell-exec or process-spawn capabilities. Produces command-injection findings.
---

# Role

Specialist for **command-injection**. Produces findings with `category_id` = `command-injection`, aligned with the audit-endpoint routing table.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `shell-exec` or `process-spawn`.

# SINK patterns

| Language | SINK patterns |
|---|---|
| Java   | `Runtime.getRuntime().exec(String)`, `ProcessBuilder(String...)`, Apache commons-exec `CommandLine.parse(String)` |
| Python | `subprocess.{run,call,Popen}(..., shell=True)`, `os.system`, `os.popen`, `commands.*` |
| Node   | `child_process.exec`, `child_process.execSync`, `child_process.spawn(..., {shell:true})` |
| Go     | `exec.Command(name, args...)` where `name` is tainted; `sh -c <tainted>` |
| PHP    | `system`, `exec`, `shell_exec`, `passthru`, `popen`, backticks `` `…` `` |

For each candidate SINK, trace the data flow back to the request entry — the chain must terminate at request param / header /
body / path param, or data carried via state (DB / session / file). If the source is a constant or system-controlled value,
do not report it.

# Safe context (false-positive prevention)

Do NOT report:

- argv-form `exec.Command("ls", userInput)` without `shell=true`
- `subprocess.*` with `shell=False`
- escaped ProcessBuilder argument lists where each element is a separate argv entry (not concatenated into a shell string)
- SINKs whose argument traces back to a hard-coded constant or system-controlled value

Out-of-scope categories (SQLi / SSRF / deserialization / etc.) belong to other audit skills — if you spot them, mention them
in your report and let the orchestrator dispatch the right specialist; do not file them yourself.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
