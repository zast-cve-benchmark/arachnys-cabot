# DWR (Direct Web Remoting) Endpoint Enumeration Reference

DWR exposes server-side Java beans/methods to the browser as AJAX endpoints under a
single servlet mount (conventionally `/dwr`). It is almost always a **second surface
alongside Spring MVC** (a project has `@Controller` pages *and* DWR services), so it is
easy to miss — enumerate it in addition to the annotation framework, never instead of.
Services are registered either in a `dwr.xml` config or by `@RemoteProxy` annotations;
the per-service prefix is known at the mount, so the main agent pre-composes L1 + the
service name and hands the worker a whole-segment scope.

---

## 1. Identify

One grep-able signal each — both agents read this, keep it short.

- **Dependency marker** — `org.directwebremoting` (or legacy `uk.ltd.getahead`) in
  `pom.xml` / gradle build.
- **Config marker** — a `dwr.xml` file (under `WEB-INF/` or the classpath), or a
  `<create .../>` / `<convert .../>` block.
- **Mount marker** — a `DwrServlet` / `DwrSpringServlet` registered to a url-pattern
  (`web.xml` `<servlet-mapping>`, or a `ServletRegistrationBean(new DwrServlet(), "/dwr/*")`).
- **Annotation marker** — `@RemoteProxy` on a class, `@RemoteMethod` on a method.

```regex
DwrServlet|DwrSpringServlet|directwebremoting|@RemoteProxy|<create\s
```

---

## 2. Structural traversal — main agent

DWR endpoints are composed from two layers:

```
{DWR servlet mount} + / + {service name}
```

### L1 Deployment — the DWR servlet mount

The mount is the DWR servlet's url-pattern, with the trailing `/*` dropped — almost
always `/dwr`. Find it at the servlet registration: `web.xml`
`<servlet-mapping><url-pattern>/dwr/*</url-pattern>`, or a Spring
`ServletRegistrationBean(new DwrServlet(), "/dwr/*")`. Compose any app context-path
before it, same as any other servlet (see project-structure.md §5). If no explicit
mapping is found, the DWR convention mount is `/dwr`.

### L3 Registration root

There is **one DWR registration root per project**: the set of services declared in
`dwr.xml`, plus any `@RemoteProxy`-annotated classes. Treat it as a single worklist
entry (one worker) — the services are small and share the one mount.

- **`dwr.xml`** — each `<create javascript="NAME" ...>` declares one service exposed as
  `NAME`. (`creator="spring"` wires it to a Spring bean via `<param name="beanName">`;
  `creator="new"` to a class — the creator doesn't change the URL, only what backs it.)
- **`@RemoteProxy`** — each annotated class is a service; its name is the annotation's
  `name`/`scriptName` attribute, or the simple class name if unset.

### Prefix composition

`{context-path} + {mount} + "/" + {service name}`. With no context-path and the default
mount: service `multiService` → `/dwr/multiService`.

### Dispatch contract
- One worklist entry = the project's DWR config (all `dwr.xml` services + `@RemoteProxy`
  classes together — one worker).
- Hand the worker: `framework=dwr`, `prefix=<context-path + servlet mount>` (e.g.
  `/dwr`), `location=<dwr.xml or the servlet-registration file:line>`,
  `scope=<the dwr.xml file and/or the @RemoteProxy class glob>`.
- Do not split per service; do not merge with the Spring-MVC worklist (different mount).

---

## 3. Handler enumeration — worker

Given the DWR mount prefix and the config scope, record one endpoint per service —
`{mount}/{service name}`, method `*` (DWR multiplexes GET/POST through the servlet).

- **`dwr.xml`**: one endpoint per `<create javascript="NAME">` → `{mount}/NAME`. The
  `javascript` attribute is the URL segment, NOT the `beanName`/class — record the
  `javascript` value. Enumerate every `<create>`; there is usually one per AJAX feature.
- **`@RemoteProxy`**: one endpoint per annotated class → `{mount}/{name}`, where `name`
  is `@RemoteProxy(name=...)`/`scriptName`, else the simple class name.
- Record at the **service** level (`/dwr/coverArtService`), not per remote method — the
  service is the addressable HTTP surface; individual methods are multiplexed under it.
- Region-anchor each entry to its `<create>` line in `dwr.xml` (or the `@RemoteProxy`
  class declaration).
