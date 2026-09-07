# JSONPath

JSONPath is a small navigation language over JSON documents. Many libraries
implement it with varying extensions:

- **Python `jsonpath-ng` / `jsonpath-rw`** — pure JSONPath, no embedded code.
- **Java `JayWay JsonPath`** — filter expressions with limited predicates.
- **Goessner-style JSONPath in JS / others** — sometimes used with
  `eval()`-style filter execution (this is the dangerous variant).

## Sink shapes

```
parse(<user>).find(data)            # python jsonpath-ng
JsonPath.read(data, <user>)          # java
jp.query(data, <user>)               # JS libraries
```

## Reachable capabilities

| Capability | Reachable? |
|---|---|
| Read environment variables | No |
| Read arbitrary files | No |
| Spawn shell / exec | **Only** if the library implements filters via host `eval()` (rare; legacy JS libs). Otherwise no. |
| Reflection | Same — only via host-`eval()` libs. |
| Navigate any node of the JSON document | **Yes** — that's the whole purpose. |

The intrinsic capability is "read arbitrary path of the document". So the
risk model depends on **what the document is**.

## Decision rules

- **The document contains data the caller wouldn't otherwise have access to**
  (other tenants' records, application secrets serialized into the JSON,
  cross-account data). → `information-disclosure`. Attacker writes a path
  that escapes the intended slice and reads forbidden fields.
- **The document is exactly the caller's own data.** → no finding. Filtering
  one's own data with one's own expression is not a vulnerability.
- **The library is a legacy JS implementation that compiles filter
  predicates via host `eval()`.** → `code-injection`. Read the library's
  filter implementation to confirm; if you can see a `Function(...)` or
  `new Function(...)` constructed from the filter substring, it is
  effectively `eval`.
- **`category_id` is NOT `el-injection`** for the pure-navigation case —
  JSONPath cannot RCE. Reserve `el-injection` for the engines that can.

## Validation patterns that are NOT sanitizers

- Library-level `parse()` success means the expression is well-formed; it
  says nothing about the paths it navigates.
- Length / regex limits on the expression do not bound traversal depth or
  prevent wildcards.

## What WOULD make a JSONPath sink safe

- Restricting the *input document* to data the caller is authorized to see.
  This is the right defense: filter at the data-fetch step, not at the
  expression-parse step.
- An expression compiler that walks the AST and rejects wildcards / parent
  references / array slicing before evaluation.
