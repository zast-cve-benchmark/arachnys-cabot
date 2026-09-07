# Java Servlet Endpoint Enumeration Reference

The Java Servlet API (`javax.servlet` / `jakarta.servlet`) is the foundation under
every Java web framework and is still used **directly** in many applications. Servlet
is a **per-class-prefix** framework: each servlet class is a registration root, and
its url-pattern is per-class — declared on the class (`@WebServlet`) or in `web.xml`,
not derived from any shared registry. So the main agent hands the worker only the L1
deployment prefix (the servlet context path); the worker composes each servlet's own
url-pattern itself. This file is split so the main agent reads §1–§2 and the worker
reads §1 + §3.

Two facts shape enumeration:

1. **Mapping and method are separate.** The URL comes from `@WebServlet` / `web.xml`.
   The HTTP method comes from which `doXxx` method the class overrides.
2. There is **no path parameter syntax** — dynamic segments arrive via path patterns
   (`/*`) and `request.getPathInfo()`.

---

## 1. Identify

One grep-able signal per layer confirms plain-Servlet usage:

- **Dependency / import marker**: the Servlet API — `javax.servlet.*` (older stacks)
  or `jakarta.servlet.*` (Servlet 5+).
- **Class marker**: a class `extends HttpServlet` (or implements `Servlet`), or a
  class carrying `@WebServlet(...)`.
- **Mapping marker**: `@WebServlet(...)` on a class, or `<servlet>` /
  `<servlet-mapping>` in `web.xml`; routed methods are the `doGet` / `doPost` /
  `doXxx` / `service` overrides.

---

## 2. Structural traversal — main agent

Walk the layer checklist for Servlet, descend to the registration-root layer, and
dispatch a worker below it. (Worker: skip to §3.)

### L1 Deployment

The deployment prefix is the **servlet context path** — the base path the whole
application mounts under. It comes from the container/deployment config. Read it from
an actual config file (cite the `file:line`); do **not** assume a convention. Common
sources:

- An **embedded-server contextPath** set in the app's own startup config — a Jetty
  `WebAppContext`/`ContextHandler` with `setContextPath("/x")` (often in a standalone
  `*/conf/jetty.xml` as `<Set name="contextPath">/x</Set>`, which may live in a
  separate `assembly`/`distribution` module from the controllers — grep the whole
  repo for `contextPath`/`setContextPath`), or a Tomcat `<Context path="/x">`. When an
  app is **always** deployed at a fixed path (e.g. a console UI fixed at `/console`,
  an API fixed at `/api`), that contextPath **is** routing — apply it.
  - **Cross-module mapping (the hard, commonly-missed case).** The contextPath often
    lives in an **assembly / distribution** module's `jetty.xml`, NOT in the module
    that holds the servlets. The link is the **`resourceBase`** beside it: a
    `contextPath=/x` paired with `resourceBase=…/webapps/x` mounts whatever war/module
    is assembled into `webapps/x`. To attribute the prefix: find the
    `contextPath`+`resourceBase` pair, take its `webapps/<name>` dir, then find which
    module produces that webapp (an assembly descriptor with `outputDirectory
    webapps/<name>`, or a war named `<name>`) — that module's servlets get this
    contextPath. So a servlet module assembled into `webapps/<name>` serves its
    handlers under `/<name>`, even though the contextPath is declared two modules away.
- A `<context-param>` in `web.xml`, or the WAR/context name.

Absent → the app mounts at `/` (`prefix=""`). Drop a contextPath only when it is a
deploy-time *default* that is routinely overridden; a stable fixed mount is kept (when
unsure, keep the cited contextPath — dropping a real mount is the worse error). In a
multi-module app each web module may declare its own context, so read the config of
every web-surface module — and the assembly/distribution module that mounts them —
not just the entry-point module's.

### L3 Registration root

Each **servlet class** is a registration root; its url-pattern is that root's prefix.
A servlet's url-pattern comes from **either** mechanism (both are additive — check
both):

- `@WebServlet("/x")` (or `urlPatterns = {...}`) on the class — Servlet 3.0+.
- a `web.xml` `<servlet-mapping>` whose `<servlet-name>` links to this class via
  `<servlet>` / `<servlet-class>`.

A third, rarer source is programmatic registration —
`context.addServlet(...).addMapping(...)` in a `ServletContextListener` /
`ServletContainerInitializer` — present in framework-free apps.

Find the roots across **all** web modules:

```bash
grep -rl '@WebServlet\|extends HttpServlet' --include='*.java' .
```

and read each module's `web.xml` (typically `src/main/webapp/WEB-INF/web.xml` or
`WebContent/WEB-INF/web.xml`) for descriptor-declared servlets.

### Prefix composition

```
endpoint = context-path (L1) + servlet url-pattern (L3) + path-info (L4)
```

Because one worker scope holds several servlet classes that do not share a url-pattern,
the main agent hands only the **L1** segment (context path); each servlet's L3
url-pattern is the worker's to compose from `@WebServlet` or `web.xml`.

### Dispatch contract
- One worklist entry = one servlet **package / directory** (or one `web.xml`), NOT
  one entry per servlet class — grouping servlets under one worker avoids worker
  explosion on large apps.
- Hand each worker: `framework=servlet`, `prefix=<this module's context path, or "">`
  (L1 ONLY — the per-servlet url-pattern is the worker's to compose),
  `location=<the servlet package dir, or the web.xml file>`,
  `scope=<the servlet package glob>`. For servlets declared in `web.xml`, point the
  worker at `web.xml` as a supporting file so it can resolve their `<url-pattern>`s.
- Split / merge: one entry per servlet package per web module. Do NOT split a package
  into per-class entries; do NOT merge two modules whose context paths differ.

---

## 3. Handler enumeration — worker

Given one root's scope, enumerate every routed handler. (Main agent: you already did
§2; skip to your next root.) At endpoint-composition time apply the main agent's **L1**
context-path prefix + **this servlet's own** url-pattern + the path-info — resolve each
servlet's url-pattern yourself from `@WebServlet` or `web.xml`.

### HTTP method ↔ servlet method

A servlet handles a method only if it overrides the corresponding `doXxx`:

| Overridden method | HTTP Method |
|-------------------|-------------|
| `doGet(req, resp)` | GET |
| `doPost(req, resp)` | POST |
| `doPut(req, resp)` | PUT |
| `doDelete(req, resp)` | DELETE |
| `doHead(req, resp)` | HEAD |
| `doOptions(req, resp)` | OPTIONS |
| `doTrace(req, resp)` | TRACE |
| `service(req, resp)` | All (dispatches to `doXxx`, or handles everything itself) |

**Enumeration rule:** for each servlet, record one endpoint per overridden `doXxx`
method, with that method. If the class overrides `service(...)` directly, it handles
**all** methods — record method `"*"`.

### Resolving each servlet's url-pattern

#### Annotation-based (`@WebServlet`) — Servlet 3.0+

```java
import jakarta.servlet.annotation.WebServlet;   // or javax.servlet.* on older stacks
import jakarta.servlet.http.HttpServlet;

@WebServlet("/users")
public class UserServlet extends HttpServlet {

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) { ... }   // GET /users

    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse resp) { ... }  // POST /users
}
```

Mapping variants:

```java
@WebServlet("/users")                              // single value
@WebServlet(urlPatterns = "/orders")               // named attribute
@WebServlet(urlPatterns = {"/items", "/products"}) // multiple patterns -> multiple endpoints
@WebServlet(name = "ApiServlet", urlPatterns = "/api/*")   // path-prefix pattern
```

Each entry in `urlPatterns` is its own URL; cross with each overridden `doXxx`.

#### Descriptor-based (`web.xml`)

```xml
<web-app>
  <servlet>
    <servlet-name>UserServlet</servlet-name>
    <servlet-class>com.example.UserServlet</servlet-class>
  </servlet>
  <servlet-mapping>
    <servlet-name>UserServlet</servlet-name>
    <url-pattern>/users</url-pattern>
    <url-pattern>/members</url-pattern>      <!-- a servlet may have several mappings -->
  </servlet-mapping>
</web-app>
```

Resolution: `<servlet-mapping>` links a `<url-pattern>` to a `<servlet-name>`, and
`<servlet>` links that name to a `<servlet-class>`. To enumerate, join the three and
then inspect the class's `doXxx` overrides.

`web.xml` lives at `src/main/webapp/WEB-INF/web.xml` (or `WebContent/WEB-INF/web.xml`).
A servlet may be mapped in **both** `@WebServlet` and `web.xml` — `web.xml` mappings
are additive. Check both.

#### Programmatic registration

```java
// In a ServletContextListener / ServletContainerInitializer
ServletRegistration.Dynamic reg = context.addServlet("UserServlet", new UserServlet());
reg.addMapping("/users", "/members");
```

`context.addServlet(...).addMapping(...)` is a third mapping source — rarer, but
present in framework-free apps.

### URL pattern semantics

| Pattern form | Meaning |
|--------------|---------|
| `/users` | Exact match |
| `/api/*` | Path-prefix match — matches `/api/anything`; record as a catch-all under `/api` |
| `*.do` | Extension match — matches any path ending `.do` |
| `/` | Default servlet (catch-all) |

For a `/*` prefix pattern, dynamic data is read inside the handler:

```java
protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
    String pathInfo = req.getPathInfo();   // the part after the mapped prefix
    String id = req.getParameter("id");    // query / form parameter
}
```

There is no `:id`-style declared path parameter — record the mapped pattern (e.g.
`/api/*`) as the endpoint.

### Filters (not endpoints)

```java
@WebFilter("/api/*")
public class AuthFilter implements Filter {
    public void doFilter(ServletRequest req, ServletResponse resp, FilterChain chain) { ... }
}
```

`@WebFilter` / `<filter>` in `web.xml` register filters — request interceptors,
**not** endpoints. Do not record them as controllers.

### Region anchoring

```java
// Standard servlet handler — fixed (request, response) signature
protected void doGet(HttpServletRequest request, HttpServletResponse response)
        throws ServletException, IOException {
    String id = request.getParameter("id");          // query/form param
    String pathInfo = request.getPathInfo();          // dynamic path segment
    BufferedReader body = request.getReader();         // request body
    response.getWriter().write("...");                 // response
}
```

The body of the routed method *is* the controller method — its `Region` is the
`doXxx` (or `service`) method definition, **not** the class header.

### Locating servlet classes

#### AST search patterns

```java
// Annotated servlets
ast_grep_search(pattern='@WebServlet($PATTERN)', lang='java')

// Servlet classes
ast_grep_search(pattern='class $NAME extends HttpServlet { $$$ }', lang='java')

// Routed methods
ast_grep_search(pattern='protected void doGet($$$) { $$$ }', lang='java')
ast_grep_search(pattern='protected void doPost($$$) { $$$ }', lang='java')
ast_grep_search(pattern='protected void doPut($$$) { $$$ }', lang='java')
ast_grep_search(pattern='protected void doDelete($$$) { $$$ }', lang='java')
ast_grep_search(pattern='protected void service($$$) { $$$ }', lang='java')
```

#### Regex search patterns

```regex
@WebServlet\s*\(
extends\s+HttpServlet
(protected|public)\s+void\s+do(Get|Post|Put|Delete|Head|Options)\s*\(
(protected|public)\s+void\s+service\s*\(
<servlet-mapping>
<url-pattern>
```

#### Key files to check

| Path | Purpose |
|------|---------|
| `src/main/webapp/WEB-INF/web.xml` | Descriptor-based servlet/filter mappings |
| `src/main/java/**/servlet/` | Servlet classes |
| `src/main/java/**/web/` | Web-layer classes |
| `src/main/java/**/*Servlet.java` | Servlet class naming convention |

### Enumeration checklist

- One endpoint **per overridden `doXxx`** — the HTTP method is the method, not the mapping.
- An overridden `service(...)` (no `doXxx`) handles all methods → record `"*"`.
- The URL comes from `@WebServlet` *and/or* `web.xml` *and/or* `addServlet(...).addMapping(...)` — check all three; mappings are additive.
- Multiple `urlPatterns` / multiple `<url-pattern>` → multiple endpoints (cross-product with each `doXxx`).
- `/*` and `*.ext` patterns are catch-alls — record the pattern as the endpoint; there is no `:id` path-parameter syntax.
- `@WebFilter` / `<filter>` are filters, not endpoints.
