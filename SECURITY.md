# Security policy and demo boundary

## Scope

This repository is a local engineering demonstration. It uses fabricated data and a demo customer selector header. It is not suitable for real banking operations, regulated production workloads, or decisions affecting a customer's access to money.

## Reporting

Do not include real credentials, customer details, card data, or trace exports in public issues. Report suspected vulnerabilities privately to the repository owner using GitHub's private vulnerability reporting when enabled.

## Safe operation

- Keep `.env` private. Rotate a credential immediately if it is committed or disclosed.
- Use synthetic customer records only. Do not load production transaction histories into the fixture database or telemetry backend.
- Keep `CAPTURE_TRACE_CONTENT=false` unless deliberately testing with fabricated prompts and responses. Telemetry data can contain sensitive content when capture is enabled.
- No tool in the application may initiate, approve, reverse, or schedule a payment.
- `X-Demo-Customer-ID` chooses one of the two local fixtures; it does not authenticate a person.
- Treat model output, retrieved documents, and logs as untrusted data.

## Production adaptations are out of scope

A production banking deployment requires institution-specific identity verification, authorization, secure secrets management, encryption and key rotation, audit retention, anti-abuse controls, data-protection review, model-risk validation, regulatory review, incident response, and operational support. This demo supplies none of those assurances.
