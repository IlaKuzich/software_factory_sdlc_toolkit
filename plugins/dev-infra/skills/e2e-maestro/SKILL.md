---
name: e2e-maestro
description: dev-infra service module (beta). Maestro end-to-end UI tests for the Expo app — Maestro CLI + Java, flows in apps/mobile/.maestro, iOS simulator and Android emulator targets, and running them locally or on the self-hosted runners. Use when adding E2E/UI tests or when Maestro runs fail on setup issues.
---

# Module: e2e-maestro

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.

**Requires:** expo (and expo-ios / expo-android for the platforms to test)

## Decisions

- **Where tests run** — locally only · on self-hosted runners in CI (recommended once `runners` is done)
  · Maestro Cloud (paid, no emulator upkeep).
- **Android emulator host** — the Android emulator inside WSL2 needs nested virtualization and is
  often unstable. Recommended: run the emulator on the Windows host and let WSL reach the Windows adb
  server (`.wslconfig`: `networkingMode=mirrored`; in WSL: `export ADB_SERVER_SOCKET=tcp:127.0.0.1:5037`).

## Steps (per machine that runs tests)

1. **Java 17+** — Check: `java -version`. Configure: see `expo-android` step 1 (also needed on macOS for Maestro).
2. **Maestro CLI** — Check: `maestro --version`.
   Configure (confirm; no sudo): `curl -Ls "https://get.maestro.mobile.dev" | bash`; add `~/.maestro/bin`
   to PATH in `~/.zshrc`. Maestro needs Java on PATH (`workstation` step 6) in the same shell.
3. **Target device** — iOS: `xcrun simctl list devices booted` has a device (boot one with `xcrun simctl boot "<name>"`).
   Android: `adb devices` lists the emulator.
4. **Flows** — Check: `apps/mobile/.maestro/*.yaml`.
   Configure: flows take `APP_ID` and optional `DEV_SERVER`. A **dev-client build** has no embedded bundle,
   so the flow must connect it to Metro first; release builds just `launchApp`:
   ```yaml
   appId: ${APP_ID}
   ---
   - runFlow:
       when: { true: "${DEV_SERVER != undefined}" }
       commands:
         - openLink: "exp+<slug>://expo-development-client/?url=${encodeURIComponent(DEV_SERVER)}"
         - tapOn: { text: "Open", optional: true }   # iOS "Open in <app>?" system dialog
   - runFlow:
       when: { true: "${DEV_SERVER == undefined}" }
       commands: [launchApp]
   - extendedWaitUntil: { visible: "<first screen text>", timeout: 60000 }
   - waitForAnimationToEnd
   ```
   After a bundle (re)load the UI can appear before it accepts taps: wrap the first navigation in
   `retry` (tap, then wait for the next screen's element). Prefer `id:` selectors (`testID`).
   Run: `maestro test -e APP_ID=<bundle>.dev -e DEV_SERVER=http://127.0.0.1:8081 apps/mobile/.maestro/<flow>.yaml`
   with Metro running (`npx expo start --dev-client`). Add an `e2e:<flow>` script to the app's package.json.
   Stability: run each new flow at least twice from a cold start (`xcrun simctl terminate booted <APP_ID>` first).
5. **Dev build installed** — iOS: simulator build from `expo-ios` (unpack the tar.gz, `xcrun simctl install booted <App>.app`);
   Android: dev APK from `expo-android` (`adb install <apk>`).
6. **CI** (if decided) — add an `e2e` job to `.github/workflows/mobile-build.yml` after the build job on
   the same runner: install the artifact, boot device, `maestro test --format junit --output report.xml`,
   upload the report. Extend `runner_doctor` expectations with `maestro` and `java`.

## Done when

`maestro test` passes the smoke flow on each selected platform.
