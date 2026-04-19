# ADR-005: Browser Session Auth for Dashboard and Analytics Reads

**Date:** 2026-04-19
**Status:** Accepted
**Deciders:** deadronos

---

## Context

Phase 2 introduced a built-in dashboard and several read-only analytics routes.

The first version required a browser or tool that could send `Authorization: Bearer <INGEST_TOKEN>` on the initial `GET /dashboard` request. That worked, but it created two UX and security problems for the actual browser path:

- standard browser navigation cannot conveniently attach a custom bearer header
- the dashboard page ended up templating the verified bearer token into HTML so client-side JavaScript could call `/analytics/**`

The project still wants to keep a single shared credential and avoid a full user-account system. It also wants to keep cookie-based auth tightly scoped so write routes do not accidentally gain ambient browser authorization.

---

## Decision

Add a small browser login flow for the built-in dashboard.

Specifically:

- add `GET /login` to render a browser login form
- add `POST /login` to validate the submitted `INGEST_TOKEN`
- issue a signed `HttpOnly` session cookie using `SESSION_SECRET`
- accept that signed session cookie on `GET /dashboard` and `GET /analytics/**`
- keep `POST /ingest/health/v1` and `GET /debug/recent` bearer-only
- keep direct bearer-header access working for API clients and power users

---

## Reasons

### Browser-native UX

The dashboard should be usable from a normal browser tab without requiring header extensions, custom fetch snippets, or manual request replay.

### Remove token exposure from dashboard HTML

Using a signed `HttpOnly` cookie allows the dashboard JavaScript to make same-origin requests without receiving the raw bearer token in a template or meta tag.

### Preserve the current API contract

Existing sender, debug, and direct API client flows continue to work with bearer auth. The browser session is an addition for UI convenience, not a replacement for the current credential model.

### Limit the blast radius of cookies

Ambient browser auth is intentionally limited to dashboard and analytics reads. Write-style routes keep explicit bearer headers so session cookies do not silently broaden access.

---

## Consequences

### Positive

- `/dashboard` becomes easy to open from any normal browser
- `/analytics/**` no longer depends on templating the bearer token into the page
- the system still uses one shared credential instead of a new account/login subsystem
- logout becomes a first-class browser action

### Negative

- the service now has session state in addition to bearer auth
- a new config secret (`SESSION_SECRET`) must be managed
- cookie settings must remain appropriate for local HTTP development and non-development environments

---

## Notes

- the session cookie name is configurable through `SESSION_COOKIE_NAME`
- session lifetime is configurable through `SESSION_MAX_AGE_SECONDS`
- the cookie is signed and `HttpOnly`; `SameSite=Lax` is used by default
- `https_only` is disabled for `development` and `test`, and enabled for non-development environments
- `POST /logout` clears the session and redirects the browser back to `/login`
