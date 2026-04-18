# ADR-002: Strict If/Else Normalizer Over Plugin Registry

**Date:** 2026-04-18
**Status:** Accepted
**Deciders:** deadronos

---

## Context

The ingest service receives webhook payloads from an Android sender. These payloads must be normalized into a canonical internal event model before storage. The normalization logic must handle at least:
- `steps`
- `heart_rate`
- `resting_heart_rate`
- `weight`

Two normalization strategies were considered:
1. **Strict if/else per record type** — hardcoded handling, raises on unknown type
2. **Extensible plugin/registry pattern** — record types registered dynamically, easy to add new types

---

## Decision

Use a **strict if/else per record type** in a single `Normalizer` class. Reject unsupported record types with a `NormalizationError`.

---

## Reasons

### YAGNI — Extensibility Is Not Needed Yet

The `idea.md` explicitly lists the 4 initial record types and calls out potential later types (distance, calories, sleep, blood oxygen, workout/session). Until a real payload with a new type actually arrives:
- The registry pattern adds indirection with no benefit
- Plugin discovery/loading logic is complexity that doesn't serve a current requirement

### Fail-Fast is Correct Behavior

Webhook senders can emit any record type. A strict normalizer that raises `NormalizationError` on unknown types is the right behavior for MVP — it makes payload mismatches visible immediately rather than silently ignoring records or storing them in a generic bucket.

### Easier to Debug

A flat if/else chain is easier to trace in a debugger than a registry lookup. For a single-developer local project, that matters more than extensibility.

### Easy to Extend When Needed

When a new record type arrives (e.g., from a real captured payload), converting to a registry is a 10-minute refactor. Building the registry now is premature.

---

## Consequences

### Positive
- Simple, readable code — one method, one if/else chain
- Fail-fast on unknown types prevents silent data loss
- No plugin discovery, no registration calls, no magic

### Negative
- Adding a new record type requires modifying `Normalizer.normalize()` directly
- No structural extension point — new types are code changes, not config changes
- If many record types arrive later, the if/else chain could grow large

---

## Alternatives Considered

| Option | Why Not Chosen |
|--------|---------------|
| Registry pattern (dict of handlers) | YAGNI — no known future types; adds indirection |
| Base Normalizer class + subclasses per type | YAGNI — single class is fine for 4 types |
| Generic map + config file | Doesn't match the fail-fast requirement |

---

## Notes

The strict normalizer was preferred at MVP stage. Future iteration should be driven by real captured payloads — if real Android sender data includes a type not yet supported, that's the signal to reconsider the architecture.
