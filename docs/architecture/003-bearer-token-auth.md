# ADR-003: Bearer Token Auth for MVP

**Date:** 2026-04-18
**Status:** Accepted
**Deciders:** deadronos

---

## Context

The service exposes protected local routes for ingest, debugging, analytics, and the built-in dashboard. It must reject unauthorized requests without forcing complex sender-side changes.

Security options considered:

1. **Static bearer token** — single secret in `INGEST_TOKEN`, checked on every request
2. **HMAC signature header** — sender signs requests with a shared secret; server verifies
3. **Per-device tokens** — each sender device gets its own token
4. **IP allowlist** — restrict to known device IPs

---

## Decision

Use a **single static bearer token** (`INGEST_TOKEN` env var) as the auth mechanism for the current local-first system.

---

## Reasons

### Proportional to the threat model

The service runs on `127.0.0.1:8787`. The primary threats are:

- accidental local misuse
- unauthorized scans or fuzzing

Against those threats, a bearer token is sufficient. HMAC or per-device tokens add complexity without proportional local-only value.

### Simplicity

Bearer token auth requires no sender-side signing logic. That keeps the Android app and the local tooling loosely coupled while the webhook format is still evolving.

### Reversibility

If a token is compromised, rotating it is just an env var change. Stronger schemes can still be introduced later without invalidating the current route structure.

### Planned future hardening remains possible

The project still leaves room for later HMAC signatures, per-device tokens, or stricter network controls when the threat model or deployment shape changes.

---

## Consequences

### Positive

- dead simple to implement and test
- works with the mock sender and local dashboard tooling
- token rotation is straightforward
- no sender-side code changes required for MVP and phase 2

### Negative

- a single token means authorized senders are not distinguishable by auth alone
- there is no per-device auth audit trail yet
- tokens live in process environment configuration

---

## Alternatives Considered

| Option | Why Not Chosen |
| ------ | -------------- |
| HMAC signature | Requires sender app changes; over-engineered for the current local scope |
| Per-device tokens | No strong multi-device auth requirement yet; adds token management complexity |
| IP allowlist | Weak protection for local workflows and easy to misconfigure |

---

## Notes

The bearer token is checked via simple string equality (`parts[1] == self.token`). Constant-time comparison was considered but not implemented because a practical timing attack against this local deployment is not the current threat model.

Protected routes currently using the bearer token:

- `POST /ingest/health/v1`
- `GET /debug/recent`
- `GET /analytics/**`
- `GET /dashboard`

The health check (`GET /healthz`) is intentionally unauthenticated so it can remain a simple probe for load balancers and health checks.
