---
name: expo-android
description: dev-infra platform module. Android target for the Expo app — where Android builds run (Windows laptop via WSL2, or this machine), JDK 17 + Android SDK, keystore via EAS, internal distribution, and optional Google Play Console. Use when adding Android or when Android builds fail on setup issues.
---

# Module: expo-android

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.

**Requires:** expo

## Decisions

- **Where Android builds run** — Windows laptop runner (WSL2, see `runners`), this machine, or both.
  Toolchain steps 1–2 apply only to machines that build Android; skip them on this machine otherwise.
- **Google Play Console** — not needed to build or to install on devices (APK / EAS internal
  distribution). Needed only for publishing. $25 one-time, identity verification takes days, and new
  *personal* accounts must run a closed test (≥12 testers, 14 days) before a production release.
  Recommend registering ~1 month before the first planned Play release; record as an open item.

## Steps

1. **JDK 17** — Check: `java -version` reports 17. Configure (macOS): `brew install --cask zulu@17`;
   (WSL/Ubuntu): `sudo apt install openjdk-17-jdk`.
2. **Android SDK** — Check: `$ANDROID_HOME/platform-tools` and `$ANDROID_HOME/build-tools` exist.
   macOS: User installs Android Studio (`brew install --cask android-studio`) and opens it once.
   WSL: command-line tools + `sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"`.
   Add `ANDROID_HOME` to the shell profile (and the runner's `.env`, see `runners`).
3. **Keystore** — Check: `eas credentials --platform android` shows a keystore for the build profile.
   Configure: EAS generates it on the first build; back it up via `eas credentials` (losing it blocks Play updates).
4. **First build** — internal APK on the build machine:
   `cd apps/mobile && eas build --local --platform android --profile development --non-interactive`.
5. **Google Play** (if decided) — User: https://play.google.com/console/signup; create the app with the prod
   package name; for automated submit, a service account JSON key stored as an EAS secret.

## Done when

The dev APK installs and launches on a device or emulator; Play status recorded (done / deferred).
