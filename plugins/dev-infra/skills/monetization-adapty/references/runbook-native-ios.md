# Adapty iOS demo — agent runbook (native SwiftUI)

> Source runbook, kept verbatim. The `monetization-adapty` skill adapts it to Expo; use this file as-is only for a
> native SwiftUI app. Differences in the Expo adaptation: state file at `.dev-infra/adapty-state.json`, SDK key via EAS
> env vars instead of `Config/Adapty.xcconfig`, `react-native-adapty` instead of the Swift SDK, the StoreKit scheme via a
> config plugin, no Xcode project step.

Goal: take an iOS demo app from nothing to "onboarding wizards + paywalls served by Adapty, purchases working in the iOS Simulator", with the human involved only where marked **[HUMAN]**.

Tools the agent needs: shell (Node.js ≥ 18, Xcode CLI), the Adapty CLI, and a browser that acts in the human's own Chrome session (Claude in Chrome) for the Apple Developer portal.

State lives in `adapty-state.json` (repo root). Read it at the start of every phase. Every ID the agent creates or looks up goes there immediately. If an entity is already recorded there, **reuse it — never create a duplicate.**

General rules:
- Stop and ask when an input is missing. Never invent IDs, names, prices or designs.
- Never accept agreements, terms or license updates on the human's behalf. Never enter passwords.
- Never modify or delete Adapty entities that are not recorded in `adapty-state.json`.
- Always pass `--json` to the Adapty CLI.

---

## Part A — Account & app setup (once per demo app)

### A1. Apple Developer: check access

1. In the browser, open `https://developer.apple.com/account/resources/identifiers/list`.
2. Outcomes:
   - **Sign-in page** → [HUMAN] ask the human to sign in in that browser, then retry.
   - **"Access Unavailable … agree to the latest Program License Agreement"** → [HUMAN] ask the human to accept it at developer.apple.com/account (only the Account Holder can). Do not click it yourself. Retry after they confirm.
   - **Identifiers list visible** → continue. Note the Team ID shown in the top-right corner.

### A2. Apple Developer: bundle ID

1. If `adapty-state.json` already has `app.bundle_id` → skip to A3.
2. [HUMAN] Ask for the bundle ID (reverse-DNS, e.g. `com.company.appname.poc`) and a description (letters, digits, spaces only; suggest `<App Name> POC`).
3. Check the Identifiers list. If the bundle ID already exists → record it and skip to A3.
4. Register it:
   - Start from the list page and click **+** next to "Identifiers" (opening the add URL directly can hang on a spinner).
   - **App IDs** → Continue → **App** → Continue.
   - Description: as agreed. Bundle ID: **Explicit**, the exact value.
   - Capabilities: change nothing. **In-App Purchase** is enabled by default for explicit IDs (greyed-out, checked). Verify it.
   - Continue → on "Confirm your App ID" verify description and `bundle-id (explicit)` → **Register**.
5. Verify the new row in the Identifiers list. Record `app.bundle_id` and `app.apple_team_id`. Close the browser tab.

### A3. Adapty CLI: install & auth

1. `adapty --version`. If missing → `npm install -g adapty`.
2. `adapty auth whoami`. If not authenticated → [HUMAN] ask the human to run `adapty auth login` in their terminal (browser device flow: match the code, click Authorize). Re-check with `whoami`.
3. Skills: if the Adapty skills (flow-generator, flow-audit, adapty-integration) are not available → `adapty skills install --agent claude-code --yes`, then [HUMAN] ask the human to restart the agent session.

### A4. Adapty app

1. If `adapty-state.json` has `app.id` → `adapty apps get <app-id> --json` to confirm it exists, then skip to A5.
2. Otherwise:
   ```bash
   adapty apps create --title "<App Name>" --platform ios --apple-bundle-id <bundle-id> --json
   ```
   Record `app.id`.

### A5. Access level

```bash
adapty access-levels list --app <app-id> --json
```
Find the entry with `sdk_id: "premium"` (created automatically with the app). Record its `id` as `access_levels.premium`. Create a different access level only if `specs/pricing.md` asks for one.

### A6. Products

Input: `specs/pricing.md` (see "Input files"). Default set if the spec only lists periods: weekly, monthly, annual.

Product ID convention: `<bundle-id>.<period>` — e.g. `com.company.appname.poc.weekly`.

For each product not yet in `adapty-state.json`:
```bash
adapty products create --app <app-id> --title "<Weekly|Monthly|Annual>" \
  --access-level-id <access_levels.premium> --period <weekly|monthly|annual> \
  --ios-product-id <bundle-id>.<period> --json
```
Record `products.<period>.id` and `ios_product_id`.

Notes:
- Store product IDs **cannot be changed** after creation. Double-check before running.
- `price_usd: 0` and `store_status: null` in the response are expected while App Store Connect is not connected. Prices for the simulator come from the StoreKit file (B2).

### A7. Public SDK key

[HUMAN] The CLI does not return the SDK key. Ask the human to copy it from app.adapty.io → the app → **App settings → General → Public SDK key** and put it in `Config/Adapty.xcconfig` as `ADAPTY_PUBLIC_KEY = <key>`. That file must be in `.gitignore`. Never write the key into `adapty-state.json`, docs or chat logs.

### A8. Xcode project

If no Xcode project exists → [HUMAN] ask the human to create an empty iOS SwiftUI app in Xcode with the bundle ID from A2 (more reliable than generating `.xcodeproj` by hand). Then add the **In-App Purchase** capability.

### A9. Agent permissions (so later phases run without prompts)

Ensure `.claude/settings.json` allows at least:
```json
{
  "permissions": {
    "allow": [
      "Bash(adapty:*)",
      "Bash(npx adapty:*)",
      "Bash(xcodebuild:*)",
      "Bash(xcrun simctl:*)",
      "Bash(swift package:*)"
    ]
  }
}
```
[HUMAN] confirms the change once.

**Part A is done when** `adapty-state.json` has the bundle ID, team ID, app ID, `premium` access level and all products; the SDK key file exists; the Xcode project builds.

---

## Part B — Build the demo (fully agentic)

Read these docs (Markdown) before each step. Never write Adapty SDK calls from memory: SDK v4 replaced paywall APIs with flow APIs.

- CLI: https://adapty.io/docs/developer-cli-reference.md
- Flows: https://adapty.io/docs/flow-generator-skill.md · https://adapty.io/docs/flow-audit-skill.md
- SDK: https://adapty.io/docs/sdk-installation-ios.md · https://adapty.io/docs/ios-quickstart-paywalls.md · https://adapty.io/docs/get-pb-paywalls.md · https://adapty.io/docs/ios-present-paywalls.md · https://adapty.io/docs/handle-paywall-actions.md · https://adapty.io/docs/ios-check-subscription-status.md · https://adapty.io/docs/ios-sdk-call-order.md
- Simulator purchases: https://adapty.io/docs/local-sk-files.md

### B1. Flows (wizards & paywalls)

Input: `specs/flows/*.md`, one file per flow.

For each flow not yet in `adapty-state.json`:
1. `adapty flows create --app <app-id> --name "<name>" --json` → record `flows.<key>.id`.
2. Build the config with the **flow-generator** skill from the spec. Paywall screens use the products from `adapty-state.json`. Images: `adapty flows media upload --app <app-id> <file>`.
3. `adapty flows config validate`, then `adapty flows config preview`. Compare with the spec.
4. Run the **flow-audit** skill and fix until it passes.
5. `adapty flows publish --app <app-id> <flow-id> --yes`, then poll `adapty flows get` until `published`. On `publication_failed`, read `adapty flows config get` and fix.

When editing an existing flow, use `--expected-updated-at` on `flows config update`.

### B2. StoreKit file (simulator purchases)

Input: `specs/pricing.md`.
1. Create `<App>.storekit` (not synced with App Store Connect): one subscription group, every product from `adapty-state.json` with the same `ios_product_id`, price and trial from the spec.
2. Create a separate scheme `<App>-StoreKit` that uses this file (Edit Scheme → Run → Options → StoreKit Configuration). The main scheme stays without it.

These purchases are local: they unlock `premium` in the app but do not appear in the Adapty dashboard. That is expected.

### B3. Placements

For each placement in the specs (default: `onboarding`, `paywall`) not yet in `adapty-state.json`:
```bash
adapty placements create --app <app-id> --title "<Title>" --developer-id "<developer-id>" \
  --audiences '[{"content_type":"flow","segment_ids":[],"flow_id":"<flow-id>","priority":0}]' --json
```
Only published flows can be attached. A placement's content type is fixed at creation.

Before any `placements update`, `paywalls update` or `segments update`: run `get --json` first and send the full payload back, because these commands replace all fields.

### B4. App integration

1. Add Adapty SDK **4.0+** via Swift Package Manager (sdk-installation-ios.md).
2. Activate at launch with `ADAPTY_PUBLIC_KEY` from `Config/Adapty.xcconfig`. Follow ios-sdk-call-order.md.
3. First launch: fetch and present the flow for placement `onboarding`. Handle close, purchase, restore and failure actions.
4. Settings screen and locked features: present placement `paywall`.
5. Gate premium features on access level `premium`.
6. Placement IDs live in one constants file. No other Adapty IDs are hardcoded.

### B5. Verify in the simulator

1. Build and run with scheme `<App>-StoreKit`: `xcodebuild` + `xcrun simctl`.
2. Take screenshots of every flow screen with `xcrun simctl io booted screenshot`.
3. Checklist:
   - [ ] Fresh install shows the onboarding flow and it matches the spec.
   - [ ] Paywall shows prices and trials from the StoreKit file.
   - [ ] Purchase succeeds and `premium` becomes active. Needs an XCUITest; without one → [HUMAN] one tap in the simulator.
   - [ ] Restore works after reinstall.
   - [ ] Closing the paywall without buying keeps the free tier.
   - [ ] Offline launch does not crash.
   - [ ] `adapty-state.json` lists every created entity.

Report as this checklist with the screenshots.

---

## Input files

| File | Contents |
|---|---|
| `specs/pricing.md` | Product set (periods), price per product, trial per product |
| `specs/flows/<key>.md` | One flow: purpose (wizard or paywall), screens in order, texts, branching, which products it shows, design references (Figma links or images in `specs/flows/assets/`) |
| `specs/placements.md` | Optional. Placement IDs and which flow each serves. Default: `onboarding` → onboarding flow, `paywall` → paywall flow |

---

## `adapty-state.json` shape

```json
{
  "app": { "id": "", "title": "", "bundle_id": "", "apple_team_id": "" },
  "access_levels": { "premium": "" },
  "products": { "weekly": { "id": "", "ios_product_id": "", "period": "weekly" } },
  "flows": { "<key>": { "id": "", "status": "" } },
  "placements": { "<developer-id>": { "id": "", "flow": "<key>" } }
}
```

---

## Later (not needed for the simulator demo)

Real sandbox purchases and data in the Adapty dashboard need: Paid Applications Agreement, the app and subscriptions in App Store Connect, In-App Purchase Key uploaded to Adapty, App Store Server Notifications, and a sandbox tester. All **[HUMAN]**.
