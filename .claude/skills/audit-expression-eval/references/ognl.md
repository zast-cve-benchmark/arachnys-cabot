# OGNL

[OGNL](https://commons.apache.org/proper/commons-ognl/) — Object-Graph
Navigation Language. Used by Struts2 and (in restricted form) by MyBatis.

## Sink shapes

```java
Ognl.parseExpression(user)
Ognl.getValue(expr, ctx, root)
OgnlUtil.setValue(user, ctx, root, value)

# Struts2:  %{<user>}  in tag attributes or value-stack lookups
# MyBatis:  ${<user>}  in XML mapper bodies (string-interpolated into OGNL)
```

Struts2 in particular evaluates `%{...}` in many places (parameter
auto-binding, redirect URLs, dynamic method invocation), so an OGNL sink
may be reached by surfaces that don't look like an expression argument.

## Reachable capabilities

| Capability | Reachable? |
|---|---|
| Read environment variables | **Yes** — `@java.lang.System@getenv("X")` |
| Read arbitrary files | **Yes** — `new java.io.FileInputStream(...)` |
| Spawn shell / exec | **Yes** — `@java.lang.Runtime@getRuntime().exec("...")` |
| Reflection / static method calls | **Yes** — `@class@method(...)` |
| Outbound network | **Yes** |

OGNL on the default `OgnlContext` is **full RCE**, equivalent to SpEL on a
StandardEvaluationContext.

## Decision rules

- **OGNL expression string is user-controlled, default context (no
  MemberAccess restriction).** → `el-injection`. OGNL on an unrestricted
  context is full RCE and maps to the `el-injection` category.
- **`SecurityMemberAccess` / `CompoundRootAccessor` configured to deny
  static-method access AND to deny direct class references.** → Read the
  config; if the deny-list actually blocks `@class@method` and `(...).class`
  patterns, no finding. Note that Struts2 has shipped many CVEs where this
  was bypassed; if you cannot confirm the patch level, prefer reporting.

## Validation patterns that are NOT sanitizers

- A regex stripping `@` characters — OGNL supports alternative syntax
  (`new java.lang.ProcessBuilder(...).start()`) without the `@` form.
- Parameter-name allowlists in Struts2 — these have repeatedly been bypassed
  via crafted parameter shapes (S2-xx CVEs).

## What WOULD make an OGNL sink safe

- A restrictive `MemberAccess` implementation that denies static-method
  invocation, constructor calls, and field access on `java.lang.*` /
  `java.io.*` / `java.net.*`. Struts2's hardened defaults are an example
  (when fully applied).
- Replacing OGNL with a non-evaluating template solution for the dynamic
  surface in question.
