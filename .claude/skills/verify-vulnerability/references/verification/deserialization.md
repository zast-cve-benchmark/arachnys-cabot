# Binary Deserialization Verification

Use for **binary deserialization vulnerabilities** only. The verification generates malicious serialized objects that trigger DNS callbacks when deserialized.

> **Important**: This method is specifically for binary serialization formats (Java native, Hessian, Kryo, Python pickle). For JSON/YAML deserialization (Fastjson, Jackson, PyYAML), use [dnslog](dnslog.md) or [regex](regex.md) verification instead.

## How It Works

1. Fetch an OOB test domain from the OOB service
2. Request malicious serialized payloads from Serialization API
3. Replace the placeholder in PoC with the generated payload
4. Execute PoC (sends payload to target web application)
5. Target application deserializes the malicious object
6. Malicious object triggers DNS query to OOB domain
7. Check if OOB domain received DNS query

## PoC Example

```python
import requests

from zast_verifier import config


if __name__ == "__main__":
    base_url = "https://example.vulnerable.web.app.com"
    payload = "%OBJ_BASE64%"  # Will be replaced with actual malicious serialized object

    response = requests.post(
        url=f"{base_url}/api/deserialize",
        data=payload,
        headers=config.get_admin_headers(),
        cookies=config.get_admin_cookies(),
    )

    print(f"Status code: {response.status_code}")
    print(f"Response text: {response.text}")
```

## Validation Command

```bash
zast-verifier validate-poc -c "%poc_code%" --method binary_deserialization --code-language java --serialization-lib native --obj-base64-placeholder "%OBJ_BASE64%"
```

## Parameters

| Parameter                 | Description                                                        | Required |
|---------------------------|--------------------------------------------------------------------|----------|
| `--method`                | Use `binary_deserialization` for this verification                 | Yes      |
| `--code-language`         | Target language (java, python)                                     | Yes      |
| `--serialization-lib`     | Serialization framework (native, hessian, kryo, pickle)            | Yes      |
| `--obj-base64-placeholder`| Placeholder in PoC to replace with malicious payload               | Yes      |
| `--env-file`              | Path to environment file (default: `~/.config/zast-verifier/.env`) | No       |

## Supported Languages & Frameworks

| Language | Framework | Description                                     |
|----------|-----------|-------------------------------------------------|
| java     | native    | Java native serialization (`ObjectInputStream`) |
| java     | hessian   | Hessian binary web service protocol             |
| java     | kryo      | Kryo serialization framework                    |
| python   | pickle    | Python pickle module (`pickle.loads`)           |

## Notes

- The placeholder must appear in the PoC code exactly as specified
- The Serialization API may return multiple payloads; verification stops at first success
- For JSON/YAML deserialization, use [dnslog](dnslog.md) or [regex](regex.md) verification
