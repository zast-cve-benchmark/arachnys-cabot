# JEXL (Apache Commons JEXL)

[JEXL](https://commons.apache.org/proper/commons-jexl/) — Apache Commons
Java Expression Language. JEXL 3 has both a sandbox and an unsandboxed mode;
many integrations use the default unsandboxed engine.

## Sink shapes

```java
JexlEngine engine = new JexlBuilder().create();
JexlExpression expr = engine.createExpression(<user>);
expr.evaluate(ctx);

// Script form:
JexlScript script = engine.createScript(<user>);
script.execute(ctx);
```

## Reachable capabilities (default builder)

| Capability | Reachable? |
|---|---|
| Read environment variables | **Yes** — `System.getenv('X')` |
| Read arbitrary files | **Yes** — JEXL allows `new()` of arbitrary classes |
| Spawn shell / exec | **Yes** — `Runtime.getRuntime().exec("...")` or `new("java.lang.ProcessBuilder", ...)` |
| Reflection / arbitrary class instantiation | **Yes** — `new('java.lang.Class')`, namespace prefixes |
| Custom namespaces | **Yes** — `ns:func(args)` syntax if the engine has functions registered |

Default `JexlBuilder().create()` is **RCE-capable**.

## Decision rules

- **Engine built with `JexlBuilder()` and no sandbox.** → `el-injection`.
- **`JexlBuilder().sandbox(new JexlSandbox(...))` configured to deny
  problematic classes.** → Read the sandbox config; if it denies the host
  classes listed above, no finding.
- **`JexlBuilder().permissions(JexlPermissions.parse("..."))` with a
  restrictive permissions string.** → Same as above; the permissions
  expression must actually exclude `java.lang.Runtime` /
  `java.lang.ProcessBuilder` / `java.io.*` / `java.net.*`.

## Validation patterns that are NOT sanitizers

- `engine.createExpression(user)` inside a try-compile validator — parse
  success means valid JEXL syntax, not safe behavior.
- Variable-binding whitelists (`JexlContext.set(name, value)`) — JEXL can
  reach unbound classes via `new(...)` regardless of which variables you
  define in the context.

## What WOULD make a JEXL sink safe

- An explicit `JexlSandbox` constructed with `READ`-only / `WRITE`-blocked
  permissions on `java.*` packages.
- A `JexlPermissions` string that allowlists only the application's own
  domain packages.
- Bounding the engine to a `JexlContext` whose `resolveNamespace` returns
  null for all namespaces.
