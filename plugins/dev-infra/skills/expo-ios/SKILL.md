---
name: expo-ios
description: dev-infra platform module. iOS target for the Expo app — Apple Developer Program, Xcode/CocoaPods/fastlane toolchain on macOS, signing credentials via EAS, and a first development build. Use when adding iOS or when iOS builds/signing fail on setup issues.
---

# Module: expo-ios

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.

**Requires:** expo

## Decisions

- **Apple Developer Program** — $99/year; needed for real devices, TestFlight, App Store
  (not for the simulator). Individual enrollment is fine for personal use. If the user doesn't
  have it yet: continue with simulator-only, mark device steps `deferred`.

## Steps

1. **Apple Developer + Team ID** — Team ID is a 10-character code (e.g. `A1B2C3D4E5`); not a secret.
   Check (automatic, try first): the Team ID is the `OU` of a signing certificate in the keychain:
   `security find-certificate -a -c "Apple Development" -p | openssl x509 -noout -subject` (also try
   "Apple Distribution"); or Xcode accounts: `defaults read com.apple.dt.Xcode IDEProvisioningTeams`.
   If several teams show up, ask which one. Nothing found → ask the user:
   - **Has a paid membership:** open https://developer.apple.com/account → sign in with the Apple ID
     used for the membership → section **Membership details** → copy **Team ID**.
     (Or App Store Connect → top-right name → Edit Profile shows Team ID too.)
     Check the account page says **Apple Developer Program** with an expiration date: if it only
     shows "Apple Developer Agreement", it's a free account and has no distribution team.
   - **Enrollment pending:** no Team ID until Apple approves (hours to ~2 days; emails about
     identity verification). Mark `deferred: Apple enrollment pending`; simulator builds work meanwhile.
   - **Not enrolled:** https://developer.apple.com/programs/enroll/ — $99/year, Apple ID with
     two-factor auth, individual enrollment is fine for personal use (organization needs a D-U-N-S number).
   Send back: the Team ID. Record: `apps.mobile.apple_team_id` and the DEVINFRA.md row note.
2. **Xcode** — Check: `xcode-select -p` is inside `Xcode.app`; `xcodebuild -checkFirstLaunchStatus` exits 0.
   User: install Xcode from the App Store; then, in a separate terminal (sudo needs a TTY):
   `sudo xcode-select -s /Applications/Xcode.app && sudo xcodebuild -runFirstLaunch`.
3. **Simulator runtime** — Check: `xcrun simctl list runtimes` has an iOS runtime.
   Configure: `xcodebuild -downloadPlatform iOS` (several GB; non-interactive, Claude can run it).
4. **CocoaPods + fastlane** — Check: `pod --version`, `fastlane --version`.
   Configure: `brew install cocoapods fastlane`.
5. **Credentials** (needs step 1; not needed for simulator builds) — Check: the user confirms (`eas credentials` is interactive only).
   User (separate terminal; interactive Apple login + 2FA): `cd <repo>/apps/mobile && eas credentials --platform ios`
   → profile `development` → "Build Credentials: Manage everything needed to build your project" → sign in →
   let EAS create the Distribution Certificate and Provisioning Profile. Device registration
   (`eas device:create`) is only needed for ad-hoc installs on a physical iPhone; skip for simulator-only.
   If Apple rejects the CLI login (EAS uses Apple's unofficial login API; it fails intermittently and usually
   recovers within hours): mark `deferred`, continue with simulator builds, and offer the **App Store Connect
   API key** path (no Apple ID login; also what CI and `eas submit` should use):
   User: https://appstoreconnect.apple.com/access/integrations/api → Team Keys → + → name `eas`, role
   App Manager → download the `.p8` (secret: keep it local, never in chat/repo). Send back Key ID + Issuer ID.
   Then (separate terminal) `eas credentials --platform ios` → App Store Connect: Manage your API Key →
   add the key (path to .p8, Key ID, Issuer ID); EAS uses it for certificates and profiles from then on.
6. **First build** — Configure: simulator build locally (no Apple credentials needed; can run while step 5 is pending):
   `cd apps/mobile && eas build --local --platform ios --profile development-simulator --non-interactive --output <scratch>/app.tar.gz`
   Takes ~10–20 min the first time. Install: unpack, `xcrun simctl boot <udid> && open -a Simulator`,
   `xcrun simctl install booted <App>.app`. A dev-client build needs Metro (`npx expo start --dev-client`)
   and is opened with `xcrun simctl openurl booted "exp+<slug>://expo-development-client/?url=http%3A%2F%2F127.0.0.1%3A8081"`;
   iOS then shows an "Open in <app>?" dialog that only a tap (user or Maestro) can confirm.

## Done when

The dev variant (`<bundle>.dev`) launches in the simulator; device build succeeds if step 1 is done.
