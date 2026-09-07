# Java Project Structure Reference

This document covers Java project layout patterns that affect controller discovery. Read this alongside the framework-specific reference (Spring, JAX-RS, Struts2, etc.) when the target is a Java project. The module map itself — which modules exist and which host a web surface — comes from the primer's `## Layout` (see §2); this reference's job is the controller **search strategy** within those modules.

---

## 1. Single-Module vs Multi-Module

### 1.1 Single-Module Layout

A single-module Java project has one `src/main/java/` tree at the root:

```
project-root/
├── pom.xml
└── src/main/java/
    └── com/example/
        ├── Application.java
        └── controller/
            ├── UserController.java
            └── OrderController.java
```

Controllers live under a single `src/main/java/` directory. Directory-based search (e.g. `src/main/java/**/controller/`) finds everything.

### 1.2 Multi-Module Layout

Maven and Gradle support multi-module projects where each module has its own `src/main/java/` tree:

```
project-root/
├── pom.xml                    # root POM with <modules>
├── module-admin/
│   ├── pom.xml
│   └── src/main/java/com/example/admin/
│       └── controller/        # controllers in this module
├── module-quartz/
│   ├── pom.xml
│   └── src/main/java/com/example/quartz/
│       └── controller/        # controllers in this module
└── module-system/
    └── src/main/java/com/example/system/
        └── service/           # no controllers (service-only module)
```

The application entry point (`@SpringBootApplication`, `main()` method, etc.) typically lives in one module. At runtime, component scanning discovers classes across **all** modules on the classpath. However, at static-analysis time, you must search all module source trees explicitly — scanning only the entry-point module will miss controllers in sibling modules.

---

## 2. The module map comes from the primer

You do not detect multi-module structure here — init-webapp already did. The
auto-loaded `CLAUDE.md` primer's `## Layout` lists every module and, for each, whether
it hosts a web surface. Enumerate the web-surface modules; skip the library / UI / CLI
/ test-only ones.

Fallback, only if `## Layout` is missing or empty: Maven multi-module shows a
`<modules>` block in the root `pom.xml`; Gradle shows `include` directives in
`settings.gradle[.kts]`. Each listed module has its own `src/` tree. If neither is
present, the project is single-module — search the single `src/main/java/` tree.

---

## 3. Controller Search Strategy for Multi-Module Projects

When the project is multi-module, **do not** search one module at a time by directory convention. Instead, grep for controller annotations across the entire project root:

```bash
# Spring Boot
grep -rl '@RestController\|@Controller' --include='*.java' .

# JAX-RS
grep -rl '@Path' --include='*.java' . | grep -v '/test/'

# Struts2 (Convention Plugin)
grep -rl '@Namespace\|@Action' --include='*.java' .
```

This finds controllers in every module regardless of directory naming conventions. Use the grep results directly to build the worklist in the framework reference's **§2 Structural traversal** — each controller class found becomes a registration root entry.

### Why grep instead of directory enumeration

- Module directories may not follow a naming pattern (`billing-svc`, `job-scheduler`, etc.).
- Controllers may live in packages named `controller`, `api`, `resource`, `rest`, `action`, or something project-specific.
- Some modules are service-only (no controllers); searching their `src/` trees wastes time.
- Grep is deterministic: you find exactly what exists, nothing more, nothing less.

---

## 4. Critical Rule

**Do not assume that the module containing the application entry point is the only module with controllers.**

This is the most common mistake in multi-module projects. The entry point module (`@SpringBootApplication`, `main()`, `Application.java`) is typically where the web server boots, but sibling modules contribute their own controllers via component scanning or package-level registration. A module with no application class can still define controllers that are active at runtime.

---

## 5. Deployment prefix (L1) — what to apply, what to skip

A Java module's config may declare several path-ish things. Only some are part of the
app's own routing (apply as the L1 prefix); others are deploy-time descriptors that the
container applies and that are routinely overridden or deployed at ROOT — those are
**not** part of routing, so record endpoints relative to the app root (`prefix=""`).

| Config | Where | L1? |
|---|---|---|
| `server.servlet.context-path` / `server.servlet.contextPath` | `application.properties`/`.yml` | **Apply** — an in-app prefix |
| `cxf.path` (and a CXF container's `setAddress`) | `application.properties` / CXF config class | **Apply** — a framework mount |
| `<servlet-mapping>` / `@WebServlet` url-pattern | `web.xml` / annotation | **Apply** — the servlet's own mapping |
| Tomcat `META-INF/context.xml` `<Context path="/x">` | the WAR's `context.xml` | **Skip** — a deploy descriptor (often overridden / deployed at ROOT) |
| the WAR filename (`foo.war` → `/foo`) | build output | **Skip** — a deploy default, not in the source's routing |

When in doubt: a value the *running framework* reads (`server.servlet.context-path`,
`cxf.path`) is L1; a value the *servlet container* reads at deploy time
(`context.xml` path, WAR name) is not. Endpoints are recorded relative to the
app root, so a `context.xml` `/myapp` or a `/<warname>` does not belong on the path.
