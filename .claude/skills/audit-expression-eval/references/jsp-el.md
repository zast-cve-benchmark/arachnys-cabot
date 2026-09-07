# JSP / Jakarta EL

Java Unified EL — the `${...}` and `#{...}` expression language used in JSP,
JSF, and CDI. Specified by JSR-341 / Jakarta EL.

## Sink shapes

```jsp
<c:set var="x" value="${<user>}"/>      <!-- re-evaluates: dangerous if user contains EL -->
<c:out value="${<user>}"/>              <!-- usually echoes the literal; safe if so -->
<jsp:setProperty name=".." value="${<user>}"/>
```

```java
ExpressionFactory.newInstance()
    .createValueExpression(elContext, "${" + user + "}", Object.class)
    .getValue(elContext);
```

The risky pattern is **constructing an EL expression by concatenating user
input into the `${...}` string**, then evaluating that string with an
`ExpressionFactory`. JSTL `<c:set>` is dangerous because it does a second
round of EL evaluation on the value.

## Reachable capabilities

EL 2.2+ allows method invocation. With a `StandardELContext`:

| Capability | Reachable? |
|---|---|
| Read environment variables | **Yes** — `${''.getClass().forName('java.lang.System').getenv('X')}` |
| Read arbitrary files | **Yes** — via class loading + reflection |
| Spawn shell / exec | **Yes** — via reflection to `Runtime.getRuntime().exec(...)` |
| Reflection | **Yes** — `getClass()` then `forName()` is the standard payload shape |

Effective RCE capability depends on the container's `ELResolver` chain.
Modern Jakarta EL implementations expose method invocation by default.

## Decision rules

- **A user-controlled string is interpolated into an EL expression that is
  later evaluated** (e.g. `value="${" + req.getParameter("x") + "}"`,
  `<c:set value="${user_value}">` where `user_value` may itself contain
  `${...}`). → `el-injection`. RCE is reachable on most modern containers.
- **The user value flows into `<c:out value="${user}"/>` only.** → this is
  XSS territory (the value is echoed into the response HTML); file under
  `audit-response-rendering`, not here.

## Validation patterns that are NOT sanitizers

- HTML-escaping the user value before EL substitution — HTML escape doesn't
  touch `${` / `#{`. EL injection survives.
- Replacing `$` with `&#36;` in the response — irrelevant; the bug is at
  evaluation time, not at HTML-render time.

## What WOULD make a JSP EL sink safe

- Not constructing EL strings from user input. Use a constant EL string
  with the user value as a bound variable: `<c:set var="x"
  value="${request.userField}"/>` where `request.userField` is treated as
  a literal property lookup, not concatenated into the EL body.
- Disabling EL evaluation entirely (`isELIgnored="true"`) on pages that
  don't need it.
