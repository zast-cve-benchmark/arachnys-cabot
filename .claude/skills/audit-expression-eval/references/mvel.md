# MVEL

[MVEL](http://mvel.documentnode.com/) — MVFLEX Expression Language. A
hybrid Java-syntax expression / template language commonly embedded in rule
engines and dynamic business-logic frameworks (Drools, jBPM).

## Sink shapes

```java
MVEL.eval(<user>, vars)
MVEL.executeExpression(MVEL.compileExpression(<user>), vars)
ParserContext ctx = new ParserContext();
MVEL.compileExpression(<user>, ctx);
```

## Reachable capabilities

| Capability | Reachable? |
|---|---|
| Read environment variables | **Yes** |
| Read arbitrary files | **Yes** |
| Spawn shell / exec | **Yes** — `Runtime.getRuntime().exec(...)` works directly |
| Reflection | **Yes** — MVEL allows full Java class access by default |
| Imports of arbitrary classes | **Yes** — MVEL's `import` directive |

MVEL is essentially a Java DSL with optional sandbox. Default config →
**full RCE**.

## Decision rules

- **`MVEL.eval(user)` / `compileExpression(user)` with default
  `ParserContext`.** → `el-injection`. RCE-capable.
- **`ParserContext` configured with `setStrongTyping(true)` AND a
  whitelist of allowed imports AND `setStrictTypeEnforcement(true)`.** →
  Read the config; if the whitelist genuinely excludes
  `java.lang.Runtime` / `java.lang.ProcessBuilder` / `java.io.*` /
  `Class.forName`-style access, no finding. This is rarely set
  comprehensively in practice; prefer reporting unless you can read the
  whole config.

## Validation patterns that are NOT sanitizers

- `MVEL.compileExpression(user)` inside a "validator" — compile success
  means the syntax is valid, not that the expression is safe.
- String-level filters for "Runtime" — MVEL supports `("Run"+"time")` and
  `Class.forName("java.lang.Runt"+"ime")`-style splits that a substring
  filter does not block.

## What WOULD make an MVEL sink safe

- A `ParserContext` with `setStrongTyping(true)`,
  `setStrictTypeEnforcement(true)`, and an `addImport(...)` allowlist
  containing only the domain types needed for the rule.
- A custom `ClassLoader` denying access to `java.lang.Runtime`,
  `java.lang.ProcessBuilder`, `java.lang.Class`, `java.io.*`,
  `java.net.*`, and similar.
