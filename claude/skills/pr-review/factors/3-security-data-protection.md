---
factor: 3-security-data-protection
title: Security & Data Protection
---

## Focus
Does this introduce vulnerabilities?

## Check for
- OWASP Top 10 risks (injection, XSS, SSRF)
- Hardcoded secrets/API keys
- Missing authorization checks
- Unsafe dependency upgrades
- PII leakage in logs
- New external dependencies (flagged here per shared discipline rule 3, regardless of which factor found them)
