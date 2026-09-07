# Test Dnslog Verification

```bash
python ./skills/craft-poc/scripts/validate_poc.py ./skills/craft-poc/tests/dnslog_poc.py --method dnslog --dnslog-domain-plh oob.oast.pro --env-file ./skills/craft-poc/tests/.env
```

# Test Regex Verification

```bash
python ./skills/craft-poc/scripts/validate_poc.py ./skills/craft-poc/tests/regex_poc.py --method regex  --pattern "root:\S:0:0:[^:]*:[^:]*:[^:]*"
```

# Test Browser-Alert Verification

```bash
python ./skills/craft-poc/scripts/validate_poc.py ./skills/craft-poc/tests/xss_poc.py --method browser-alert --env-file ./skills/craft-poc/tests/.env --alert-msg zast-xss-marker
```