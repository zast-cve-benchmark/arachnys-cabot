---
name: audit-xml-parse
description: Audit endpoints with xml-parse capability. Produces xxe-injection findings.
---

# Role

Specialist for **xxe-injection**. Produces findings with `category_id` = `xxe-injection`, aligned with the audit-endpoint
routing table.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `xml-parse`.

# SINK patterns

| Language | SINK | Key config |
|---|---|---|
| Java | `DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(user)` | Must set `setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)` to be safe |
| Java | `SAXParserFactory.newInstance().newSAXParser().parse(user, handler)` | Same as above |
| Python | `xml.etree.ElementTree.fromstring(user)`, `lxml.etree.fromstring(user, parser=lxml.etree.XMLParser())` | lxml disables DTD by default but explicit `resolve_entities=True` enables it |
| Node | `libxmljs.parseXml(user, {noent: true})` | `noent: true` is the vulnerability |
| PHP | `DOMDocument::load(user)`, `simplexml_load_string(user, ..., LIBXML_NOENT)` | `LIBXML_NOENT` is the vulnerability |
| .NET | `XmlDocument.LoadXml(user)` with `XmlResolver` non-null | |

Key check: is DOCTYPE / external-entity / DTD resolution disabled.

For each candidate SINK, trace the data flow back to the request entry — the chain must terminate at request param /
header / body / path param, or data carried via state (DB / session / file). If the source is a constant or
system-controlled value, do not report it.

# Safe context (false-positive prevention)

Do NOT report:

- Java parsers explicitly hardened with `disallow-doctype-decl = true`, or `external-general-entities` /
  `external-parameter-entities` set to `false`
- lxml `XMLParser(resolve_entities=False, no_network=True)` or defusedxml usage (`defusedxml.ElementTree`, etc.)
- PHP `libxml_disable_entity_loader(true)` before parsing, or absence of `LIBXML_NOENT`
- .NET `XmlDocument` with `XmlResolver = null`
- SINKs whose argument traces back to a hard-coded constant or system-controlled value

Out-of-scope categories belong to other audit skills — XSLT processing is its own concern; raw SQL -> `audit-sql-query`.
If you spot them, mention them in your report and let the orchestrator dispatch the right specialist; do not file them
yourself.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
