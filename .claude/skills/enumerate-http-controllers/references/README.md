# Reference structure contract

Every `references/<lang>/<framework>.md` follows the SAME three-section shape so the
main agent and the worker each read only their half. Defined once here; every
reference must conform.

## The top-down layer vocabulary (owned by SKILL.md, summarized here)

The main agent walks four layers top-down for every framework; it descends to the
registration-root layer and dispatches a worker below it.

- **L1 Deployment** — base paths applied before any code: context-path,
  servlet-mapping, framework mount (`cxf.path`), reverse-proxy prefix. From config
  files, per module. Contributes a URL prefix.
- **L2 Module** — which build modules host a web surface. From the primer's
  `## Layout`. Scopes WHERE to look; contributes no URL segment (except convention
  frameworks, where the package IS the prefix → that is L3).
- **L3 Registration root** — the framework unit binding a prefix to a set of
  handlers (a `@Controller` class, an `include_router()`, an `AutoBindRoutes`
  package, a Struts `<package>`, an `initializeHandlers()`). **Each root = one
  worklist entry = one worker.** Contributes a URL prefix.
- **L4 Handler** — each routed method + its region. Worker territory.

Final endpoint = L1 prefix + L3 prefix + method path. Dispatch boundary is L3→L4.

**per-class-prefix annotation frameworks (Spring, JAX-RS):** one worklist entry
groups several controller classes under one worker scope; the main agent hands only
the **L1** prefix, and the worker derives each class's L3 prefix
(`@RequestMapping`/`@Path`) itself — multiple classes in one scope cannot share a
pre-composed prefix.

**convention / imperative frameworks (JFinal, Struts, imperative):** the prefix is
per-root, so the main agent pre-composes **L1 + L3** and hands the whole segment.

## The three sections

## 1. Identify   (both agents read; keep short)

How to confirm this framework is in use: dependency marker (pom/package.json),
import marker, annotation / route-registration marker — one grep-able signal each.

## 2. Structural traversal — main agent (粗活; main reads, worker SKIPS)

Walk the layer checklist for THIS framework:

- L1 Deployment: where this framework's base path lives (or "none — mounts at /").
- L3 Registration root: what IS a root here, the grep to find them, how its prefix
  is derived.
- Prefix composition: how L1 + L3 compose for this framework (placeholder example).

### Dispatch contract        (MANDATORY uniform footer)

- One worklist entry = `<the framework's root unit>`.
- Hand each worker: `framework=<id>`, `prefix=<composed per the rule above>`,
  `location=<root decl site file:line>`, `scope=<glob/package/file>`.
- Split / merge rule: when to split one root into several entries, when NOT to
  over-split (each worker is one round-trip; too many exhaust the message budget).

## 3. Handler enumeration — worker (细活; worker reads, main SKIPS)

Given one root's scope: what counts as a routed handler, how to compose the final
endpoint (apply the prefix!), transitive-closure rule (base classes / meta-annotations),
region anchoring, framework quirks.

---

## Conversion status — all references follow this template

Every reference now carries the three-section shape. **Per-class-prefix annotation**
frameworks (main hands L1 only, worker composes the class prefix):
`java/spring`, `java/jaxrs`, `java/servlet`, `javascript/nestjs`.
**Convention / router-mount / imperative** frameworks (main pre-composes L1 + the
root prefix): `java/jfinal`, `java/struts2`, `java/play`, `java/imperative-routing`,
all of `go/*` (gin/echo/gorilla/fiber/chi/nethttp), `python/{flask,fastapi,django,tornado}`,
`javascript/{express,koa,fastify}`. **File-as-route** (URL path from the file path):
`php/raw-php`, `javascript/nextjs`. **Scattered call-site** (one worker per directory
a project-wide grep returns): `javascript/meteor-restivus`.

When adding a new framework reference, follow this contract: §1 Identify, §2
Structural traversal + the mandatory `### Dispatch contract` footer, §3 Handler
enumeration. Decide its prefix nature (per-class annotation → main hands L1 only;
convention/imperative/router-mount → main pre-composes L1+L3). Keep the prose general
(placeholder examples, no real codebase names as rules).
