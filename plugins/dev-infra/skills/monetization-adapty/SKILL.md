---
name: monetization-adapty
description: dev-infra service module (beta). Subscriptions with Adapty for the Expo iOS app — Adapty CLI + skills, Apple bundle ID, Adapty app, access level, products, onboarding/paywall flows built from specs with the flow-generator and flow-audit skills, placements, react-native-adapty integration, and simulator purchases via a local StoreKit file. Use when adding in-app purchases, paywalls, onboarding wizards or Adapty to a project, or when that setup is incomplete.
---

# Module: monetization-adapty

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.
Scope now: **purchases in the iOS Simulator only** (local StoreKit file). Real sandbox purchases are in "Later".
For a native SwiftUI app (no Expo), follow [references/runbook-native-ios.md](references/runbook-native-ios.md) instead.

**Requires:** expo-ios (dev-client builds, Apple Team ID). Status: **beta — not yet validated end to end.**

## Rules (from the runbook; non-negotiable)

- State lives in **`.dev-infra/adapty-state.json`** (shape below). Read it at the start of every step; write every ID
  you create or look up immediately; if an entity is recorded, **reuse it — never create a duplicate**.
- Never invent IDs, names, prices, texts or designs: stop and ask when an input is missing.
- Never accept agreements/terms or enter passwords for the user. Never modify or delete Adapty entities that are not
  in the state file. Always pass `--json` to the Adapty CLI.
- Never write Adapty SDK calls from memory (SDK v4 replaced paywall APIs with flow APIs): read the docs listed below first.
- The Public SDK key never goes into chat, the state file, docs or git.

## Decisions

- **Which bundle ID Adapty uses** — store product IDs are `<bundle-id>.<period>` and **can't be changed** later.
  For simulator tests use the dev variant (`<bundle>.dev`, already used by the dev build). One Adapty app per
  environment is the clean option once real purchases matter; record the choice.
- **Inputs exist?** `specs/pricing.md`, `specs/flows/<key>.md` (+ `specs/flows/assets/`), optional `specs/placements.md`
  (format: see "Input files"). Without them, stop after step A5 and ask.

## Part A — accounts and catalog

A1. **Apple Developer access** — the user opens https://developer.apple.com/account/resources/identifiers/list.
   Sign-in page → user signs in. "Access Unavailable … Program License Agreement" → only the Account Holder can accept;
   the user does it, never Claude. Prefer Claude in Chrome (`workstation` step 7: `/chrome` in the session) so Claude
   drives the portal in the user's signed-in browser; without it, give the user the steps.
A2. **Bundle ID registered** — check the Identifiers list. If missing: `+` next to Identifiers (opening the add URL
   directly can hang) → App IDs → App → description `<App Name> POC` (letters/digits/spaces) → Bundle ID **Explicit**,
   exact value → capabilities unchanged (In-App Purchase is on by default for explicit IDs; verify) → Register.
   (EAS may already have registered it during `eas credentials`/first device build — check before creating.)
   Record `app.bundle_id`, `app.apple_team_id`.
A3. **Adapty CLI + skills** — `adapty --version` (else `npm install -g adapty`); `adapty auth whoami --json`
   (else the user runs `adapty auth login` in a separate terminal: browser device flow). Skills flow-generator,
   flow-audit, adapty-integration: if missing, `adapty skills install --agent claude-code --yes`, then the user
   restarts the Claude session.
A4. **Adapty app** — state has `app.id` → `adapty apps get <id> --json`. Else
   `adapty apps create --title "<App Name>" --platform ios --apple-bundle-id <bundle-id> --json` → record `app.id`.
A5. **Access level** — `adapty access-levels list --app <id> --json` → the entry with `sdk_id: "premium"` (auto-created)
   → record `access_levels.premium`. Create another only if `specs/pricing.md` asks.
A6. **Products** (from `specs/pricing.md`; default periods weekly, monthly, annual) — for each not in state:
   `adapty products create --app <id> --title "<Weekly|Monthly|Annual>" --access-level-id <premium> --period <period>
   --ios-product-id <bundle-id>.<period> --json` → record `products.<period>.{id,ios_product_id}`. Confirm the IDs with
   the user before running (permanent). `price_usd: 0` / `store_status: null` are expected without App Store Connect.
A7. **Public SDK key** — the CLI doesn't return it. User: app.adapty.io → the app → App settings → General → Public SDK
   key, then in a separate terminal:
   `cd <repo>/apps/mobile && eas env:create --environment development --name EXPO_PUBLIC_ADAPTY_KEY --visibility sensitive --scope project`
   (prompts for the value) and `eas env:pull --environment development` (→ `.env.local`, gitignored).
   It's a client-side key, but treat it as sensitive anyway.
A8. **Permissions** — propose adding to the project's `.claude/settings.json` `permissions.allow`:
   `Bash(adapty:*)`, `Bash(npx adapty:*)`, `Bash(xcodebuild:*)`, `Bash(xcrun simctl:*)`. The user confirms once.

## Part B — flows, integration, simulator

Docs to read before each step (Markdown):
CLI https://adapty.io/docs/developer-cli-reference.md ·
flows https://adapty.io/docs/flow-generator-skill.md, https://adapty.io/docs/flow-audit-skill.md ·
Expo SDK https://adapty.io/docs/sdk-installation-react-native-expo.md,
https://adapty.io/docs/react-native-quickstart-paywalls.md, https://adapty.io/docs/react-native-get-pb-paywalls.md,
https://adapty.io/docs/react-native-present-paywalls.md, https://adapty.io/docs/react-native-handle-paywall-actions.md,
https://adapty.io/docs/react-native-use-fallback-paywalls-expo.md ·
simulator https://adapty.io/docs/local-sk-files.md

B1. **Flows** (one per `specs/flows/<key>.md`, not yet in state): `adapty flows create --app <id> --name "<name>" --json`
   → record; build the config with the **flow-generator** skill from the spec (paywall screens use products from state;
   images: `adapty flows media upload --app <id> <file>`); `adapty flows config validate` → `adapty flows config preview`,
   compare with the spec; run **flow-audit** until it passes; `adapty flows publish --app <id> <flow-id> --yes` and poll
   `adapty flows get` until `published` (on `publication_failed`: `adapty flows config get`, fix). Editing an existing
   flow: `flows config update --expected-updated-at`.
B2. **Placements** (default `onboarding`, `paywall`; or `specs/placements.md`), not yet in state:
   `adapty placements create --app <id> --title "<Title>" --developer-id "<dev-id>" --audiences
   '[{"content_type":"flow","segment_ids":[],"flow_id":"<flow-id>","priority":0}]' --json`. Only published flows attach;
   content type is fixed at creation. Before any `placements|paywalls|segments update`: `get --json` and send the full payload.
B3. **SDK in the Expo app** — `npx expo install react-native-adapty expo-build-properties`; app config plugins:
   `react-native-adapty` and `expo-build-properties` with `ios.useFrameworks: "dynamic"`, `ios.deploymentTarget` ≥ 15.0
   (check against what the project already sets). Native change → new dev build (see `expo-ios` step 6).
   Code (per the docs, not memory): `adapty.activate(process.env.EXPO_PUBLIC_ADAPTY_KEY)` once at startup and await it
   before any other call; first launch → flow for placement `onboarding` (handle close, purchase, restore, failure);
   settings / locked features → placement `paywall`; gate features on access level `premium`; placement IDs in one
   constants file, no other Adapty IDs in code. Bundle fallback flows (`adapty fallbacks`, Expo fallback guide) so an
   offline first launch doesn't crash.
B4. **StoreKit file for the simulator** (Expo-specific, **to validate**) — Adapty documents only the Xcode UI path.
   Plan: commit `apps/mobile/storekit/<App>.storekit` (not synced with App Store Connect; one subscription group; every
   product from state with the same `ios_product_id`, price and trial from the spec) and a local config plugin that, on
   prebuild, copies it into `ios/` and sets `StoreKitConfigurationFileReference` in a dedicated `<App>-StoreKit` scheme
   (main scheme without it). Risk to check first: Xcode applies the scheme's StoreKit config when it (or `xcodebuild`)
   launches the app; launches by Maestro/`simctl` may hit the real (sandbox) store instead. If so, drive purchases from
   an XCUITest run via `xcodebuild test -scheme <App>-StoreKit`, or `SKTestSession`. Record what works as a decision.
   Local purchases unlock `premium` in the app but never appear in the Adapty dashboard — expected.
B5. **Verify in the simulator** — build/run the StoreKit scheme; screenshot every flow screen
   (`xcrun simctl io booted screenshot`); checklist: fresh install shows onboarding matching the spec · paywall shows
   prices/trials from the StoreKit file · purchase activates `premium` (automated per B4, else one user tap) · restore
   after reinstall · closing the paywall keeps the free tier · offline launch doesn't crash · state file lists every
   entity. Report as this checklist with screenshots. Add a Maestro flow for the non-purchase paths (`e2e-maestro`).

## Done when

The B5 checklist passes; `.dev-infra/adapty-state.json` is complete; DEVINFRA.md records the bundle-ID choice and the
StoreKit approach (B4).

## Input files

| File | Contents |
|---|---|
| `specs/pricing.md` | product set (periods), price per product, trial per product |
| `specs/flows/<key>.md` | one flow: purpose (wizard or paywall), screens in order, texts, branching, products shown, design references (Figma links or images in `specs/flows/assets/`) |
| `specs/placements.md` | optional: placement IDs and the flow each serves (default `onboarding`, `paywall`) |

## `.dev-infra/adapty-state.json`

```json
{
  "app": { "id": "", "title": "", "bundle_id": "", "apple_team_id": "" },
  "access_levels": { "premium": "" },
  "products": { "weekly": { "id": "", "ios_product_id": "", "period": "weekly" } },
  "flows": { "<key>": { "id": "", "status": "" } },
  "placements": { "<developer-id>": { "id": "", "flow": "<key>" } }
}
```

## Later (real purchases; all user actions)

Paid Applications Agreement; app + subscriptions in App Store Connect; In-App Purchase Key uploaded to Adapty;
App Store Server Notifications; a sandbox tester; then one Adapty app per environment.
