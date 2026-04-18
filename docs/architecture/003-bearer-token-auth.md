# ADR-003: Bearer Token Auth for MVP

**Date:** 2026-04-18
**Status:** Accepted
**Deciders:** deadronos

---

## Context

The ingest endpoint `POST /ingest/health/v1` receives webhook payloads from a single known sender (the Android Health Connect app). It must reject unauthorized requests.

Security options considered:
1. **Static bearer token** — single secret in `INGEST_TOKEN`, checked on every request
2. **HMAC signature header** — sender signs requests with a shared secret; server verifies
3. **Per-device tokens** — each sender device gets its own token
4. **IP allowlist** — restrict to known device IPs

---

## Decision

Use a **single static bearer token** (`INGEST_TOKEN` env var) as the auth mechanism for MVP.

---

## Reasons

### Proportional to Threat Model

The service runs on `127.0.0.1:8787`. The primary threat is:
- Accidental exposure (another local app accidentally posting malformed data)
- Script kiddie / fuzzing (unauthorized scanning tools)

Against these, a bearer token is sufficient. HMAC or per-device tokens add complexity without proportional benefit for a local-only service.

### Simplicity

Bearer token auth requires zero setup beyond setting an env var. HMAC requires the sender to sign payloads with a shared secret — which means changes to the Android app. For an MVP that wants to iterate quickly, that coupling is undesirable.

### Reversibility

If a token is compromised, rotating it is a one-line env var change. HMAC key rotation requires the same, but also assumes the sender can be updated to use the new key — which may not be true for a phone/watch app.

### Planned for Later

The `idea.md` explicitly lists future enhancements (HMAC signatures, per-device tokens, IP allowlist) as non-MVP items. This decision defers that complexity without preventing it.

---

## Consequences

### Positive
- Dead simple to implement and test
- Works with the mock sender trivially
- Token rotation is a one-line change
- No sender-side code changes required

### Negative
- Single token means any authorized sender can impersonate any other
- No audit trail of which device sent a request
- Token appears in process env — visible in `/proc/*/environ` on Linux systems

---

## Alternatives Considered

| Option | Why Not Chosen |
|--------|---------------|
| HMAC signature | Requires sender app changes; over-engineered for local MVP |
| Per-device tokens | No multi-device scenario in MVP; adds token management complexity |
| IP allowlist | Local IPs are trivial to spoof; doesn't add real security |

---

## Notes

The bearer token is checked via a simple string equality (`parts[1] == self.token`). Constant-time comparison was considered but not implemented for MVP — if a timing attack against `127.0.0.1` is a real threat, the threat model has bigger problems.

The debug route (`GET /debug/recent`) also requires auth — same bearer token. The health check (`GET /healthz`) is unauthenticated, which is intentional: it's meant to be a simple probe for load balancers and health checks.
