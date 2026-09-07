# JNDI Injection

Inject malicious JNDI/LDAP/RMI URLs that cause the target application to load and execute remote code.

## Dnslog Verification

Construct HTTP requests that send **malicious JNDI URLs** to the target. When the target performs JNDI lookup, it loads a URLDNS gadget from the exploit server, triggering a DNS callback.

> See [JNDI Injection Verification](../verification/jndi.md) for workflow and validation.

## Common Scenarios

- Log4j vulnerabilities: `${jndi:ldap://...}`
- Direct JNDI lookup endpoints
- RMI/RMI-IIOP deserialization

## Key Points

1. Use `jndi` verification method
2. Placeholder must be the complete JNDI URL
3. Supports `ldap://`, `rmi://`, `dns://` schemes
