# Spring Expression Language (SpEL)

[SpEL](https://docs.spring.io/spring-framework/reference/core/expressions.html)
is a full-featured expression language in the Spring framework with direct
access to Java classes, reflection, and method invocation.

## Sink shapes

```java
new SpelExpressionParser().parseExpression(user).getValue(...)
expressionParser.parseExpression(user).getValue(ctx, Object.class)
@Value("#{<user>}")  // when the literal #{...} body comes from user input
```

Less obvious sinks:
- Spring Security annotations (`@PreAuthorize("...")`) when the annotation
  argument is user-controlled — possible during dynamic AOP setups.
- Spring Data query annotations (`@Query("...")` with SpEL expansion).

## Reachable capabilities

SpEL by default uses `StandardEvaluationContext`, which exposes:

| Capability | Reachable? |
|---|---|
| Read environment variables | **Yes** — `T(java.lang.System).getenv("X")` |
| Read arbitrary files | **Yes** — `new java.io.FileInputStream("/etc/passwd")` |
| Spawn shell / exec | **Yes** — `T(java.lang.Runtime).getRuntime().exec("...")` |
| Reflection / call any Java method | **Yes** |
| Outbound network | **Yes** — `new java.net.URL(...).openStream()` |
| Class loading | **Yes** — `T(java.lang.Class).forName(...)` |

SpEL on a `StandardEvaluationContext` is **Turing-complete remote-code
execution**. Any user-controlled expression evaluated by it is a critical
finding.

## Decision rules

- **`StandardEvaluationContext` (default) or any context that allows
  `T(...)` references / method calls on `java.*`.** → `el-injection`. SpEL
  is the canonical RCE-capable EL family; this is the bucket it belongs in.
- **`SimpleEvaluationContext` (intentionally restricted) AND the builder
  doesn't add back risky resolvers.** → Read the builder to confirm. If the
  context truly blocks type references and method invocation, there is no
  finding.

Do not split SpEL by impact (exec vs file-read vs env-read). The engine is
RCE-capable end-to-end; report `el-injection` once per undefended endpoint.

## Validation patterns that are NOT sanitizers

- `parseExpression(user)` inside a "syntax check" — this just confirms the
  expression parses. `T(Runtime).getRuntime().exec("id")` parses fine.
- Token allowlists / regex filters on the surface string — SpEL accepts many
  equivalent forms (`T(java.lang.Runtime).getRuntime()` vs
  `''.getClass().forName('java.lang.Runtime')...`); a string-level filter
  almost never closes all paths.

## What WOULD make a SpEL sink safe

- Switching to `SimpleEvaluationContext` built with only the property /
  index accessors required by the use case (no `addMethodResolver`, no
  `addDataBindingPropertyAccessor`).
- An AST visitor that walks the parsed expression and rejects
  `TypeReference` nodes, `MethodReference` nodes, and constructor calls
  before evaluation.
- Replacing SpEL entirely with a simple template / property lookup if the
  use case only needs `${name}`-style substitution.
