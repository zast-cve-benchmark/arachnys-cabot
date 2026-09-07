# Deserialization

Inject malicious serialized objects that execute code or trigger callbacks when deserialized by the target application.

## Binary Deserialization

For Java native serialization, Hessian, Kryo, Python pickle, etc.

Construct HTTP requests that send **base64-encoded serialized objects** to the target. When deserialized, the malicious object triggers a DNS callback.

> See [Binary Deserialization Verification](../verification/deserialization.md) for workflow and validation.

## String Deserialization

For Fastjson, Jackson, Gson, XStream, JAXB, XMLDecoder, PyYAML, SnakeYAML, etc.

Construct HTTP requests that send **malicious string payloads** (JSON, YAML, XML) that trigger RCE/SSRF/file read via template injection or gadget chains.

> See [DNS Log Verification](../verification/dnslog.md) or [Regex Verification](../verification/regex.md) for workflow and validation.

## Key Points

1. **Binary**: Use `binary_deserialization` method
2. **String**: Use `dnslog` or `regex` method
3. **Content-Type**: Binary uses `application/octet-stream`; String uses corresponding MIME type (`application/json`, `text/yaml`, `application/xml`, etc.)
