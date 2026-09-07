---
name: audit-deserialize
description: Audit endpoints with binary-deserialize or string-deserialize capabilities. Produces insecure-deserialization findings.
---

# Role

Specialist for **insecure-deserialization**. Produces findings with `category_id` = `insecure-deserialization`, aligned with
the audit-endpoint routing table.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `binary-deserialize` or `string-deserialize`.

# SINK patterns

| Form | Language | SINK |
|---|---|---|
| Java native | Java | `ObjectInputStream.readObject()`, Apache commons-collections gadgets present |
| XStream / Jackson | Java | `XStream.fromXML(user)` without forbidding dangerous classes, `ObjectMapper.enableDefaultTyping()` + `readValue(user, Object.class)` |
| fastjson | Java | `JSON.parseObject(user, Object.class)` with autoType enabled |
| SnakeYAML | Java | `new Yaml().load(user)` (vs safe `new Yaml(new SafeConstructor()).load(...)`) |
| pickle | Python | `pickle.loads(user)`, `pickle.load(user_stream)`, `cPickle.loads(user)` |
| yaml | Python | `yaml.load(user)` default Loader (PyYAML < 5.1), `yaml.load(user, Loader=yaml.Loader)` |
| Node | Node | `node-serialize`'s `unserialize(user)`, `js-yaml.load(user, {schema: js_yaml.DEFAULT_FULL_SCHEMA})` |
| PHP unserialize | PHP | `unserialize($user)` when classes contain `__wakeup`/`__destruct` |
| Go gob | Go | `gob.Decoder.Decode(&obj)` from untrusted source (rare) |

For each candidate SINK, trace the data flow back to the request entry — the chain must terminate at request param /
header / body / path param, or data carried via state (DB / session / file). If the source is a constant or
system-controlled value, do not report it.

# Safe context (false-positive prevention)

Do NOT report:

- `yaml.safe_load(user)` / `yaml.load(user, Loader=yaml.SafeLoader)` (Python)
- `new Yaml(new SafeConstructor()).load(...)` (Java SnakeYAML)
- `js-yaml.load(user)` with the default safe schema
- Jackson `ObjectMapper` **without** `enableDefaultTyping()` and **without** polymorphic `@JsonTypeInfo` on user-reachable types
- fastjson with `autoType` disabled and no `@type` whitelist bypass
- SINKs whose argument traces back to a hard-coded constant or system-controlled value

Out-of-scope categories belong to other audit skills — XML parse with external entity -> `audit-xml-parse`; raw SQL/NoSQL
-> `audit-sql-query`. If you spot them, mention them in your report and let the orchestrator dispatch the right
specialist; do not file them yourself.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
