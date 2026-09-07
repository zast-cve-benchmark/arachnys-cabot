# jq

[jq](https://jqlang.github.io/jq/) is a JSON query language commonly embedded
in apps via libraries such as Python `jq`, Go `gojq`, Node `node-jq`.

## Sink shapes

```
jq.compile(<user>).input(data).all()
jq.compile(<user>).input(data).first()
gojq.Parse(<user>); code.Run(input)
```

Any code path that takes a user-controlled string and passes it to
`compile` / `Parse` of a jq library, then evaluates against some JSON input.

## Reachable capabilities

| Capability | Reachable from a jq expression? |
|---|---|
| Read process environment variables | **Yes** — `env.<NAME>`, `$ENV.<NAME>` |
| Read arbitrary files on disk | No (in normal embedded mode — `input`/`inputs` only read from streams the host passed in) |
| Spawn shell / exec processes | No |
| Reflection / call host functions | No |
| Outbound network | No |
| Modify host objects | No |

jq is intentionally a pure data-transformation language. It cannot RCE.
The one host-facing capability that matters is **environment-variable
access**.

## Decision rules

- **Result of the expression is rendered back into the HTTP response (or
  written to a place the attacker reaches) AND the engine has env access.**
  → `information-disclosure`. The attacker can exfiltrate environment
  variables (API tokens, database URIs, signing keys, etc.) by writing
  `.env.SECRET_NAME` and reading the response body / stored value.
- **Result is not echoed (blind eval, side effects only).** → typically no
  finding. jq has no side-effecting builtins worth reporting. Do not invent
  a category just to file something.
- **`category_id` is NOT `el-injection`.** jq cannot RCE; the broader bucket
  is reserved for engines that can. Use `information-disclosure`.

## Validation patterns that are NOT sanitizers

- A `jq.compile(user)` call inside a "validator" that only catches parse
  errors — this just confirms the expression parses; `env.X` parses fine.
- Regex/character allowlists that permit dots, brackets, and alphanumerics —
  `env.SECRET` is alphanumeric+dot.

## What WOULD make a jq sink safe

- Wrapping the compiled program in a host-level transform that strips or
  rejects expressions referencing `env`, `$ENV`, `getpath(["env",...])`
  before evaluation. Read the wrapper; confirm the AST/string check
  actually blocks env access. A name like "safe_jq" is not enough — open
  the file.
- Running jq in a process boundary with `env -i` (empty environment) before
  invocation, so even if the expression reads `env`, there is nothing to
  read.
