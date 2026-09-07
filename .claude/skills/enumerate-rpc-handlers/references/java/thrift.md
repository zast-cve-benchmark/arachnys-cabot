# Apache Thrift Handler Enumeration Reference (Java)

## Overview

Apache Thrift generates a server-side stub from a `.thrift` IDL file. Each IDL `service` block
produces a Java interface (`XService.Iface`) and a processor (`XService.Processor`). The
application implements that interface in a handler class and registers the processor on a
`TMultiplexedProcessor` (or a plain `TProcessor` for single-service servers). Every method
declared in the IDL `service` block is one RPC source.

---

## 1. IDL → handler method mapping

A Thrift IDL service method maps **name-for-name** to a Java handler method. Case is preserved:
an IDL method `createFile` → Java method `createFile`. There is no name translation (unlike gRPC).

```thrift
// my_service.thrift
service MyService extends common.BaseService {

  CreateResponse createItem(
    1: string path,
    2: CreateOptions options,
  ) throws (1: exception.AppException e)

  DeleteResponse deleteItem(
    1: string path,
    2: DeleteOptions options,
  ) throws (1: exception.AppException e)
}
```

The generated interface `MyService.Iface` declares the same method signatures.
The handler class implements this interface:

```java
// MyServiceHandler.java
public final class MyServiceHandler
    implements MyService.Iface {

  @Override
  public CreateResponse createItem(final String path, final CreateOptions options)
      throws AppException {
    return RpcUtils.call(LOG, () -> {
      mService.createItem(new AppURI(path), new CreateOptions(options));
      return new CreateResponse();
    }, "CreateItem", "path=%s, options=%s", path, options);
  }

  @Override
  public DeleteResponse deleteItem(final String path, final DeleteOptions options)
      throws AppException {
    return RpcUtils.call(LOG, () -> {
      mService.deleteItem(new AppURI(path), new DeleteOptions(options));
      return new DeleteResponse();
    }, "DeleteItem", "path=%s, options=%s", path, options);
  }
}
```

**The `region` for each method is the handler impl method body — not the IDL, not the generated
`*Service.java` stub, not the `RpcUtils.call(...)` wrapper class.**

---

## 2. Identifying the handler class

The Thrift generator creates `XService.Iface`; the application provides exactly one class that
`implements XService.Iface`. Find it:

```bash
# Find all classes that implement an Iface (Thrift handler pattern)
grep -rl 'implements.*\.Iface' --include='*.java' .

# Or grep specifically for the service you found in the IDL
grep -rn 'implements MyService\.Iface' --include='*.java' .
```

The result is typically a single class, often named `*ServiceHandler` or `*ServiceImpl`.
Open that class — it is `handler_location`.

---

## 3. Service registration root

The handler is wired into the Thrift server via a `Processor` and registered on a
`TMultiplexedProcessor`. In projects that host many master/worker services:

```java
// MasterProcess.java — the registration root
protected void startRpcServer() {
    TMultiplexedProcessor processor = new TMultiplexedProcessor();
    for (Master master : mRegistry.getServers()) {
        registerServices(processor, master.getServices());  // iterates a map
    }
    // ...
}

private void registerServices(TMultiplexedProcessor processor, Map<String, TProcessor> services) {
    for (Map.Entry<String, TProcessor> service : services.entrySet()) {
        processor.registerProcessor(service.getKey(), service.getValue());
        // key = IDL service name (e.g. "MyService")
        // value = new MyService.Processor(handlerImpl)
    }
}
```

In simpler single-service projects the registration is more direct:

```java
XService.Processor<XServiceHandler> processor =
    new XService.Processor<>(new XServiceHandler());
TServer server = new TSimpleServer(
    new TServer.Args(serverSocket).processor(processor));
```

The service name used in `registerProcessor(name, ...)` must match the IDL `service` name. **Use
the IDL name as `service` in the output, not the impl class name and not the registration key if
they differ (though they should not).**

---

## 4. Method list source — always the IDL, not the impl class

The IDL is the authoritative method list. The impl class may have private helpers, lifecycle
methods (e.g. `getServiceVersion`, `getServiceName`), and framework-generated boilerplate that
are not RPC methods. **Read the IDL `service` block to enumerate methods; use the impl class only
to find each method body's start/end lines.**

The `extends` clause in the IDL (e.g. `service X extends common.BaseService`) adds inherited
methods from the base service. Open the base service's `.thrift` file to include those methods —
the handler class implements them too.

```bash
# List all service method names in a .thrift file
grep -E '^\s+(void|[A-Z][a-zA-Z]+Response|[a-z][a-zA-Z]+TResponse)\s+\w+\(' \
  path/to/service.thrift
```

---

## 5. `region` — always the handler method body

For every IDL method, the `region` points at the method body in the handler impl class:

- `region.file_path`: relative path to the handler Java file (NOT the `.thrift`, NOT the generated
  `XService.java`)
- `region.start_line`: the `@Override public XxxTResponse methodName(...)` signature line
- `region.end_line`: the closing `}` of that method

**Why this matters for downstream auditing:** the call-graph completion step reads `region` and
walks outward into delegated-to methods (e.g. `mService.createItem(...)`). Starting from
the IDL or a generated shim would give the auditor zero application logic to analyze.

**Delegation is fine — stay at the handler boundary.** If the handler body is simply
`return mMaster.doSomething(path, options)`, record the handler method body at those lines. The
auditor will follow the delegation. Do not recurse into `mMaster` and record those methods instead
— that would collapse every RPC method onto the shared master class and lose per-method granularity.

---

## 6. Multi-service projects

A project may expose several Thrift services (e.g. a storage master may expose a `FileService`,
`BlockService`, `MetaService`, each with its own handler class). Each
service becomes its own worklist entry and its own worker dispatch. Never merge two services into
one worker.

```bash
# Find all .thrift service definitions in the project
grep -rn '^service ' --include='*.thrift' .
```

---

## 7. Enumeration checklist

- Read the IDL `service` block (and any base service via `extends`) — that is the authoritative method list.
- Find the impl class via `implements XService.Iface` grep.
- For each IDL method, locate the `@Override` method body in the impl class.
- Record `service` = IDL service name, `method` = IDL method name (case-sensitive), `region` = handler method span.
- Do NOT record the IDL `.thrift` file as the region.
- Do NOT record the generated `XService.java` as the region.
- Do NOT skip `getServiceVersion` / version-negotiation methods — they are RPC methods and potential attack surface.
