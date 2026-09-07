# Spring Boot Actuator Configuration Audit Reference

Used by audit-stack when LANGUAGE=java, FRAMEWORK=spring-boot-actuator. Covers Actuator endpoint exposure, sensitive endpoint security, and management server config.

## Actuator Endpoint Exposure

Actuator endpoints expose operational information. They're designed for ops teams to monitor health, metrics, and configuration.

Key endpoints and what they reveal:
- `/actuator/env` — all environment variables
- `/actuator/heapdump` — full heap dump (all in-memory data)
- `/actuator/configprops` — all configuration properties
- `/actuator/gateway/routes` — gateway route configuration (writable in some versions)
- `/actuator/jolokia` — JMX-over-HTTP bridge; in older Spring Boot versions without security configuration, allows arbitrary MBean method invocation (potential RCE), not just information disclosure.

Key points to trace:
- Which actuator endpoints are enabled?
- Are they accessible without authentication?
- Is the actuator base path changed from the default `/actuator`?

## Output

- `management.endpoints.web.exposure.include=*` or sensitive endpoint exposed without authentication → `information-disclosure`
- Sensitive endpoint (`/actuator/env`, `/actuator/heapdump`, `/actuator/jolokia`) reachable on the public port → `information-disclosure`
- `management.endpoints.web.cors.allowed-origins=*` → `cors-misconfiguration`
