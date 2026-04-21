# Dashboard Figma Alignment Plan

**Date:** 2026-04-19  
**Branch:** `feat/dashboard-figma-alignment`  
**Figma reference:** `https://www.figma.com/design/wVGJGxJeIyO3khUG6IVMGB/fitness-dashboard--Community-?node-id=55-123&p=f&t=XkirCmgrhwQQvjHo-0`  
**Reference node:** `55:123`

## Goal

Make the built-in `/dashboard` feel substantially closer to the referenced fitness dashboard while preserving the current architecture:

- FastAPI route rendering via Jinja2
- vanilla JavaScript for data fetching and rendering
- existing `/analytics/**` APIs as the primary data source
- current browser-session auth model for `/login`, `/dashboard`, and `/analytics/**`

This is a **UI alignment project first**, not a database or API redesign.

## Current State

Today the dashboard is functional but intentionally plain:

- `app/templates/dashboard.html` renders a light-themed, single-column analytics page
- `app/static/dashboard.css` defines one shared style sheet for both login and dashboard views
- `app/static/dashboard.js` renders:
  - a generic overview card grid
  - a simple SVG time-series bar chart
  - a recent-events table
- `app/routes/dashboard.py` and `app/routes/browser_auth.py` already provide the routing and auth behavior needed for a richer UI

### Current visual gaps vs. Figma

The Figma reference is a very different composition from the current page:

- dark gradient shell instead of light analytics panels
- fixed left navigation rail
- denser multi-column layout rather than stacked sections
- large hero/summary cards instead of generic record-type tiles
- stylized metric cards for calories, heart, and water
- bottom activity section with multiple compact charts/stat cards
- stronger art direction: softer pastels, rounded surfaces, depth, profile area, and visual hierarchy

## Figma Breakdown

From the Figma metadata and screenshot, the reference screen is roughly organized as:

- **Left rail** (`116px` wide): logo + vertical icon navigation
- **Top header**: title/subtitle on the left, profile chip on the right
- **Upper-left hero card**: activity summary (“Morning Walk”)
- **Upper-left secondary cluster**: four small nutrition tiles
- **Center feature card**: body/health summary panel with illustration and measurements
- **Upper-right stack**: calories, heart, and water cards
- **Bottom full-width section**: activity tracking + total time + total distance + average speed

## Important Constraint: Data Availability

The current product has richer analytics data than the first dashboard shell, but it still does **not** map 1:1 to every concept in the Figma comp.

### Available today from existing routes/data

- record-type overview stats (`count`, `sum`, `avg`, `min`, `max`, latest values)
- timeseries buckets for a chosen record type
- recent normalized events with `metadata`
- health domains already modeled in the project include, among others:
  - `steps`
  - `heart_rate`
  - `resting_heart_rate`
  - `active_calories`
  - `total_calories`
  - `nutrition`
  - `weight`
  - `height`
  - `body_fat`
  - `lean_body_mass`
  - `exercise`

### Not guaranteed today

- a dedicated profile model like the Figma “Jenny Wilson / Student” card
- a first-class body-illustration asset
- consistently present nutrition data for all fixtures/users
- exact semantic matches for every Figma card label

Because of that, implementation should aim for **layout and experience parity**, while using graceful fallbacks when specific record types are missing.

## Context Map

### Files to Modify

| File | Purpose | Likely Changes |
| ------ | ------- | -------------- |
| `app/templates/dashboard.html` | Dashboard structure | Replace stacked analytics layout with rail + header + multi-panel grid while keeping stable DOM hooks for JS |
| `app/static/dashboard.css` | Shared UI styles | Introduce dark-shell design language, responsive grid, card variants, charts/gauges, and scoped login/dashboard theming |
| `app/static/dashboard.js` | Dashboard rendering | Map analytics responses into Figma-like cards, gauges, highlight tiles, and improved empty states |
| `app/templates/login.html` | Browser auth screen | Optional visual refresh so login and dashboard feel like the same product |
| `tests/test_dashboard.py` | Dashboard route coverage | Keep auth behavior tests, update/extend content assertions for the refreshed UI shell |
| `tests/test_browser_auth.py` | Login/logout behavior | Update only if login markup text changes materially |
| `README.md` | Product description | Update dashboard description once implementation ships |
| `CHANGELOG.md` | User-facing changes | Add one-line entry once the UI refresh is implemented |

### Dependencies

| File | Relationship |
| ------ | ------------ |
| `app/routes/dashboard.py` | Serves `dashboard.html` and should remain behaviorally stable |
| `app/routes/browser_auth.py` | Serves `login.html`; shared styling changes may affect login UX |
| `app/routes/analytics.py` | Existing JSON APIs should remain the primary data source |
| `app/schemas.py` | Defines current analytics response shape; avoid changing unless Phase 4 is approved |
| `docs/architecture/004-analytics-read-model.md` | Confirms dashboard is built on FastAPI + current analytics read model |
| `docs/architecture/005-browser-session-auth-for-dashboard.md` | Confirms current auth/session behavior that UI work must preserve |

### Test Files

| Test | Coverage |
| ---- | -------- |
| `tests/test_dashboard.py` | `/dashboard` auth and HTML response |
| `tests/test_browser_auth.py` | `/login` and `/logout` behavior |
| `tests/test_analytics_routes.py` | Data endpoints the refreshed UI depends on |

### Reference Patterns

| File | Pattern |
| ---- | ------- |
| `app/static/dashboard.js` | Current approach for fetching analytics data and rendering cards/charts without adding a frontend build step |
| `app/templates/login.html` | Existing shared template conventions and CSS reuse |
| `docs/plans/2026-04-19-phase-2-analytics-dashboard-plan.md` | Prior planning style used in this repo |

### Risk Assessment

- [ ] Breaking changes to public API
- [ ] Database migrations needed
- [ ] Configuration changes required

No architectural change is expected for the first pass. The main risk is scope creep from “closer to the Figma” into “new dashboard product model.”

## Recommended Target State

Implement the refresh in **three practical tiers**.

### Tier 1 — Shell and Layout Fidelity

Get the dashboard visually into the same family as the reference without changing backend contracts.

- dark gradient background and elevated card surfaces
- left navigation rail
- top header with title, subtitle, auth/profile area, and logout affordance
- responsive three-zone dashboard grid
- more expressive typography, spacing, shadows, and rounded corners

### Tier 2 — Data-to-Card Mapping

Translate existing analytics data into more editorial cards.

- convert overview data into card types such as calories, heart, activity, and summary tiles
- use timeseries data for the bottom activity section
- keep the recent events table, but move it lower on the page or into a secondary panel so it stops dominating the visual hierarchy
- use empty-state copy when a record type is unavailable instead of forcing a misleading placeholder

### Tier 3 — Optional High-Fidelity Enhancements

Only after Tier 1 and Tier 2 feel solid:

- center “body stats” feature card with either:
  - approved design assets from Figma, or
  - a lightweight abstract visual treatment if asset reuse is not available
- more specific nutrition/body-composition groupings if current data proves reliable
- subtle hover/transition polish

## Refactor Plan: Dashboard Design Alignment

### Existing Implementation

The dashboard is a functional analytics surface with a light theme, stacked panels, generic section headings, and simple SVG charting. It already has working auth, data routes, and tests, so the main work is presentational and front-end rendering logic.

### Target State

The dashboard keeps the same route/auth/data model, but the page is restructured into a dark, high-contrast, multi-panel fitness dashboard closer to the Figma reference. It should feel intentional and product-like while still working when only some health record types are available.

### Affected Files

| File | Change Type | Dependencies |
| ------ | ----------- | ------------ |
| `app/templates/dashboard.html` | modify | depends on current JS hooks and CSS classes |
| `app/static/dashboard.css` | modify | affects `dashboard.html` and `login.html` |
| `app/static/dashboard.js` | modify | depends on `/analytics/**` responses |
| `app/templates/login.html` | optional modify | depends on shared CSS strategy |
| `tests/test_dashboard.py` | modify | depends on final semantic markup |
| `tests/test_browser_auth.py` | optional modify | depends on login copy/markup changes |

## Execution Plan

### Phase 1: Layout and Semantic Structure

- [ ] Rebuild `app/templates/dashboard.html` into a shell that mirrors the Figma composition:
  - left rail
  - top header
  - hero/activity card
  - center feature card
  - right metric stack
  - bottom analytics row
  - secondary recent-events area
- [ ] Keep stable IDs or data attributes for JavaScript mounting points so route behavior remains unchanged
- [ ] Verify: `tests/test_dashboard.py` still passes or only needs text-level updates

### Phase 2: Styling System and Responsive Behavior

- [ ] Rework `app/static/dashboard.css` for the new visual direction:
  - dark shell background
  - pastel/accent card variants
  - card elevation and rounded corners
  - responsive desktop-to-tablet collapse behavior
  - improved table and empty-state styling
- [ ] Decide whether login keeps the shared stylesheet or receives a clearly scoped subset of the same system
- [ ] Verify: dashboard and login remain readable on narrow screens; no auth flow regressions

### Phase 3: Front-End Presenter Logic

- [ ] Add presenter helpers in `app/static/dashboard.js` that transform the existing overview/timeseries/event payloads into dashboard-specific view models
- [ ] Prioritize mappings such as:
  - `total_calories` / `active_calories` → calories card
  - `heart_rate` / `resting_heart_rate` → heart card
  - `nutrition` / water-related events if present → small stat tiles
  - `exercise` / `steps` / distance-like series → hero and bottom activity visuals
  - `weight`, `height`, `body_fat`, `lean_body_mass` → center body summary card
- [ ] Keep a generic fallback card path so unsupported data still surfaces cleanly
- [ ] Verify: dashboard renders meaningful content against current fixture-driven data, not only ideal data

### Phase 4: Stretch Fidelity (Optional)

- [ ] If visual parity still feels short, add one approved illustration strategy for the center card
- [ ] If current analytics APIs are insufficient for a specific card, document the exact missing field before changing any backend contracts
- [ ] Verify: any proposed API extension is deliberate, minimal, and documented before coding

### Phase 5: Tests and Docs

- [ ] Update `tests/test_dashboard.py` to assert durable semantics (landmarks/headings/key shell labels), not brittle cosmetic strings
- [ ] Update `tests/test_browser_auth.py` only if login text/markup changes materially
- [ ] Run targeted verification:
  - `pytest tests/test_dashboard.py tests/test_browser_auth.py tests/test_analytics_routes.py -q`
- [ ] When implementation ships, update:
  - `README.md`
  - `CHANGELOG.md`
  - any doc text that describes the built-in dashboard UX in a materially outdated way

## Rollback Plan

If the redesign becomes unstable or too scope-heavy:

1. Revert `app/templates/dashboard.html`, `app/static/dashboard.css`, and `app/static/dashboard.js` together as a single UI unit.
2. Keep `app/routes/dashboard.py`, analytics routes, and auth/session behavior unchanged.
3. Re-introduce visual changes in smaller slices: shell first, then card mapping, then optional illustration work.

## Key Risks and Mitigations

- **Risk:** Figma semantics do not match live health data.
  - **Mitigation:** Design cards around existing record types first; hide or downgrade unsupported sections gracefully.

- **Risk:** Shared CSS causes accidental login regressions.
  - **Mitigation:** Scope dashboard shell classes carefully or split login-specific styles if the stylesheet becomes tangled.

- **Risk:** Chasing pixel-perfect parity pulls in backend work.
  - **Mitigation:** Treat backend/API changes as a separate approval checkpoint, not part of the first UI pass.

- **Risk:** The center body card requires assets that are not available in the repo.
  - **Mitigation:** Use an abstract card or lightweight inline illustration for the first pass unless assets are explicitly approved for import.

## Recommendation

The best first implementation is:

1. **Tier 1 shell/layout refresh**
2. **Tier 2 data mapping using existing analytics routes**
3. **Defer any backend changes or exact-asset parity unless the refreshed UI still feels insufficient**

That approach gets the dashboard much closer to the Figma reference without turning a styling task into an accidental product rewrite.