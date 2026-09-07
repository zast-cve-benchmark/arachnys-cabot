---
name: enumerate-rpc-handlers
description: Enumerate all RPC handler methods (gRPC/Thrift/Dubbo) in a project and record each as a source for security auditing. Use when the user asks to "enumerate RPC handlers", "list all gRPC/Thrift/Dubbo services", "find all RPC methods", "extract RPC attack surface", or when an audit pipeline needs to cover RPC/IDL-defined services alongside HTTP controllers.
---

# Enumerate RPC Handlers

## Task

Traverse the codebase to find all gRPC, Thrift, and Dubbo service handlers. For each RPC method declared in the IDL (or service interface), record the handler method body as a source entry.
The output file is fixed by the host and read directly by the recording script — you never name it (see Output).

---

## Arguments

This skill takes no arguments.

## Output

You never specify, pass, or echo the output file path. `record_rpc_handlers.py` reads the authoritative path from the host-injected `ZAST_ENUMERATION_SOURCES_FILE` env var, so records always land in the right file regardless of your working directory. Just run the script without `-o`. (The script uses file-level locking, so the file is safely shared with the HTTP controller enumerator.)

---

## Expected Results

The result file is a JSON list — one entry per RPC handler method, with its service name, method name, framework, and source location.

**You (the orchestrator) never write this file, so you do not carry the field-level schema.** Every record goes through an `enumerate-rpc-handlers-worker` sub-agent (step 4), and the schema — the exact field names, types, and required/optional rules — lives in that worker's definition, because the worker is the only thing that records and the only thing that needs it. This keeps one authoritative schema (mirrored by `scripts/record_rpc_handlers.py`, which validates each item on write, and by `vuln_spec.RpcHandlerSource`, which `llm-auditor` parses the file back into). Your job is the worklist and the dispatch, not the JSON shape.

---

## Workflow

### 1. Detect RPC framework(s) — cheap no-op gate

Before reading any source files in depth, grep for the presence of each RPC framework. **Most projects are HTTP-only; a fast negative here is the common, cheap case — stop and report "no RPC frameworks found" rather than doing expensive code reads for a technology that isn't present.**

Run these checks (adapt paths to the language as needed):

```bash
# gRPC: .proto files containing service+rpc declarations
grep -rl 'service\b' --include='*.proto' . | head -5
# gRPC: Java/Go/Python deps
grep -rE 'io\.grpc|grpc-java|grpcio|google\.golang\.org/grpc' \
  pom.xml build.gradle go.mod requirements.txt 2>/dev/null | head -5

# Thrift: IDL files
find . -name '*.thrift' | head -5
# Thrift: Java/Python deps
grep -rE 'libthrift|org\.apache\.thrift|thrift' \
  pom.xml build.gradle requirements.txt 2>/dev/null | head -5

# Dubbo: service annotations or deps
grep -rE '@DubboService|@Service.*dubbo|org\.apache\.dubbo|com\.alibaba\.dubbo' \
  --include='*.java' --include='*.xml' . 2>/dev/null | head -5
```

If **none** of these hit, STOP. Report "no RPC frameworks found — project appears to use HTTP only" and record nothing. Do not proceed to step 2.

If one or more hit, note which frameworks are present and continue.

**Scope — do not exclude "example" / "demo" / "sample" modules.** Enumerate RPC
services wherever they are defined, including `examples/`, `demo/`, `sample/`, and
`*-examples-*` / `*-demo-*` submodules. Bundled example/demo services are real,
deployable handler surface and part of the audit scope — do NOT dismiss a detected
`.proto` or Dubbo service as "just an example / not the core library" and skip it.
(The HTTP enumerator includes such modules; this one must match, or its whole
surface silently drops to zero.)

### 2. Load matching reference(s)

For each framework detected in step 1, read the matching reference — one per framework actually in use. Do not preload sibling references for frameworks the project does not use.

- Thrift (Java): `$PWD/.claude/skills/enumerate-rpc-handlers/references/java/thrift.md`
- gRPC (Java): `$PWD/.claude/skills/enumerate-rpc-handlers/references/java/grpc.md`
- Dubbo (Java): `$PWD/.claude/skills/enumerate-rpc-handlers/references/java/dubbo.md`

The reference covers how IDL methods map to handler methods, what counts as the handler impl class vs the generated shim, and how method names translate between the IDL and Java (especially the gRPC PascalCase → camelCase gotcha). One read is enough; re-derive from the worklist rather than reopening.

### 3. Map service registration roots → worklist

For each framework in use, find the service registrations and build one worklist entry per IDL service.

**Thrift:**
- Locate `.thrift` files; each `service X { ... }` block names a service.
- Find where the Thrift server registers processors: `TMultiplexedProcessor.registerProcessor("X", new XService.Processor(handlerImpl))`, or a helper like `registerServices(processor, master.getServices())` that iterates a map of `(serviceName → TProcessor)`. The registration root in projects hosting many master/worker services is often a `startRpcServer()` or `registerServices()` method.
- The handler class is the one implementing `XService.Iface` — typically named `*ServiceHandler` or similar. Its file path is `handler_location`.
- Worklist entry: `{framework: thrift, service: X, idl_location: path/to/x.thrift, handler_location: path/to/XServiceHandler.java:line, scope: path/to/XServiceHandler.java}`.

**gRPC (Java):**
- Locate `.proto` files; each `service X { rpc ... }` block names a service.
- Find where the gRPC server registers services: `serverBuilder.addService(new XImpl())`, or a `BindableService` Spring bean.
- The generated base class is `XGrpc.XImplBase`; the handler class extends it (`class XImpl extends XGrpc.XImplBase`).
- Worklist entry: `{framework: grpc, service: X, idl_location: path/to/x.proto, handler_location: path/to/XImpl.java:line, scope: path/to/XImpl.java}`.

**Dubbo:**
- The service interface is the IDL — a plain Java interface `interface X { ... }`.
- The handler class implements `X` and carries a Dubbo service annotation. **Detection gotcha:** the annotation is frequently the **bare `@Service`** whose Dubbo-ness lives in the IMPORT (`com.alibaba.dubbo.config.annotation.Service` or `org.apache.dubbo.config.annotation.Service`) — textually identical to Spring's `@Service`, so grepping `@DubboService` alone misses it. Also seen: `@DubboService`, and a gateway/framework may add its own export-marker annotation (a `@*DubboClient`-style marker) on top. Detect via the Dubbo annotation IMPORT, not just `@DubboService`:
  `grep -rlE 'import (org\.apache|com\.alibaba)\.dubbo\.config\.annotation\.Service|@DubboService' --include='*.java' .`
  then for each hit, the class that `implements X` is the handler.
- The same service interface is often implemented in several modules (alibaba vs apache, annotation vs XML variants) — each impl is a handler, but they collapse to ONE `service.method` identity, so enumerating any one impl per method suffices.
- Worklist entry: `{framework: dubbo, service: X, idl_location: path/to/X.java, handler_location: path/to/XImpl.java:line, scope: path/to/XImpl.java}`.

Build the worklist and print it as plain text before dispatching. One entry per service — if a project has three Thrift services, that is three entries, each dispatched to its own worker.

### 4. Dispatch one worker per worklist entry — in parallel when possible

*DO NOT* read handler source files or IDL files directly in this phase, and *DO NOT* call `record_rpc_handlers.py` yourself. Every recording goes through an `enumerate-rpc-handlers-worker` sub-agent, dispatched via the `Agent` tool with `subagent_type` set to `enumerate-rpc-handlers-worker`. The worker — not you — owns the output schema.

For each worklist entry, dispatch a worker with:

- **framework**: `thrift` | `grpc` | `dubbo`
- **service**: the IDL service name (verbatim from the IDL)
- **handler_location**: file path and line of the handler impl class
- **idl_location**: file path of the `.thrift` / `.proto` / Java interface
- **scope**: the file or directory bounding the handler search (usually just the handler class file)

(The output file is not a dispatch parameter — the worker's `record_rpc_handlers.py` reads it from the host-injected `ZAST_ENUMERATION_SOURCES_FILE` env var.)

**Dispatch workers in parallel** when their scopes do not overlap. `record_rpc_handlers.py` uses file-level locking, so concurrent writes are safe.

**Never dispatch workers with worktree isolation.** Do NOT pass `isolation: "worktree"`. A git worktree is a fresh checkout of tracked files only — it does not contain the deployed `.claude/skills/enumerate-rpc-handlers/` bundle (scripts + references are untracked), so a worker placed in one cannot find `record_rpc_handlers.py` or its reference doc and silently records nothing. Dispatch every worker in the main workspace, no isolation.

### 5. Finalize and report

This skill does **not** run deduplication — the HTTP controller enumerator (`enumerate-http-controllers`) handles dedup for the shared `SOURCES_FILE`. Report completion once all workers have finished. Do not re-read or re-parse SOURCES_FILE.
