# ADR-002: Strict If/Else Normalizer Over Plugin Registry

**Date:** 2026-04-18
**Status:** Accepted
**Deciders:** deadronos

---

## Context

The ingest service receives two webhook shapes today:

1. A flat `records` payload used by fixtures and compatibility tests
2. A nested Android Health Connect payload emitted by the sender app

Both formats must be normalized into the same canonical internal event model before storage. The runtime now accepts the full Android record set currently produced by the app:

- `steps`
- `sleep`
- `heart_rate`
- `heart_rate_variability`
- `distance`
- `active_calories`
- `total_calories`
- `weight`
- `height`
- `oxygen_saturation`
- `resting_heart_rate`
- `exercise`
- `nutrition`
- `basal_metabolic_rate`
- `body_fat`
- `lean_body_mass`
- `vo2_max`

The canonical event contract also preserves optional event-level details when available:

- `deviceId`
- `externalId`
- `fingerprint`
- optional `metadata` for record-specific details such as exercise type

Two normalization strategies were considered:

1. **Strict if/else per record type** — hardcoded handling, raises on unknown type
2. **Extensible plugin/registry pattern** — record types registered dynamically, easy to add new types

---

## Decision

Use **strict, hardcoded normalization paths** rather than a plugin or registry abstraction.

- `Normalizer` handles the flat `records` payload
- `AndroidPayloadNormalizer` handles the nested Android payload
- Both paths reject unsupported record types with `NormalizationError` or by omitting malformed records that are missing required fields

---

## Reasons

### YAGNI — Extensibility Still Does Not Need a Registry

The runtime has grown beyond the original 4-type MVP, but it still has a known and finite set of record types driven by actual sender payloads. That means:

- The registry pattern still adds indirection with no present benefit
- Plugin discovery/loading logic is still complexity that does not serve a current requirement
- Updating one strict normalizer module remains easier to debug than following dynamic registration across many handlers

### Fail-Fast is Correct Behavior

Webhook senders can emit any record type. A strict normalizer that raises `NormalizationError` on unknown types is the right behavior for MVP — it makes payload mismatches visible immediately rather than silently ignoring records or storing them in a generic bucket.

### Easier to Debug and Keep in Sync

Small, explicit normalization branches are easier to trace in a debugger than a registry lookup. For a local-first project with architecture docs kept close to implementation, that matters more than maximizing extension points.

### Easy to Extend When Needed

When a new record type arrives (e.g., from a real captured payload), converting to a registry is a 10-minute refactor. Building the registry now is premature.

---

## Consequences

### Positive

- Simple, readable code — explicit branches for each supported type
- Fail-fast on unknown flat record types prevents silent data loss
- Canonical events preserve useful fields like `deviceId`, `fingerprint`, and optional `metadata`
- No plugin discovery, no registration calls, no magic

### Negative

- Adding a new record type still requires code changes in the normalizer module
- No structural extension point — new types are code changes, not config changes
- If the sender payload surface keeps expanding, the explicit branches may eventually deserve a different organization

---

## Alternatives Considered

| Option | Why Not Chosen |
| ------ | -------------- |
| Registry pattern (dict of handlers) | YAGNI — no known future types; adds indirection |
| Base Normalizer class + subclasses per type | YAGNI — single class is fine for 4 types |
| Generic map + config file | Doesn't match the fail-fast requirement |

---

## Notes

The strict normalizer approach was preferred at MVP stage and remains the current decision for Phase 2. Future iteration should still be driven by real captured payloads — if the sender starts emitting many more types or record-specific metadata becomes substantially more complex, that is the signal to reconsider the architecture rather than preemptively introducing a plugin system.
