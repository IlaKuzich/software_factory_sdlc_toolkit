---
name: firebase
description: dev-infra platform module. Sets up the Firebase backend — one Firebase project per environment, Blaze billing with budget alerts, required APIs, Firestore, Authentication, Cloud Functions package, and app registrations for enabled platforms. Use when adding Firebase to a project, adding an environment, or when Firebase setup is incomplete.
---

# Module: firebase

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.
Config conventions: `${CLAUDE_PLUGIN_ROOT}/skills/environments/references/firebase.md`.
`<env>` = each environment in the spec, `<id>` = its `firebase_project`.

**Requires:** project-repo

## Decisions

- **Project IDs** — default `<slug>-<env>`; globally unique and permanent. If taken, propose `<slug>-<env>-<4 chars>`.
- **Region** — Firestore location and Functions region, closest to users
  (e.g. `eur3` + `europe-west1` for the EU). **Irreversible for Firestore.**
- **Billing account** — from `gcloud billing accounts list` (OPEN ones). Monthly budget alert amount.
- **Auth providers** — Email/Password, Google, Apple (Apple is required by App Store rules if other social logins are offered on iOS).

## Steps (per environment)

1. **Project** — Check: `firebase projects:list --json` contains `<id>`.
   Configure (confirm): `firebase projects:create <id> --display-name "<Name> <env>"`.
2. **Billing (Blaze)** — Check: `gcloud billing projects describe <id>` → `billingEnabled: true`.
   Configure (confirm, costs money): `gcloud billing projects link <id> --billing-account <acct>`;
   Budget: first `gcloud services enable billingbudgets.googleapis.com --project <id>`, then
   `gcloud billing budgets create --billing-account <acct> --display-name <id> --budget-amount <N>USD --filter-projects projects/<id> --threshold-rule percent=0.5 --threshold-rule percent=0.9 --threshold-rule percent=1.0 --billing-project <id>`
   (without `--billing-project` the call fails on quota project). If linking fails with a quota error,
   the billing account hit its project limit: User requests an increase at
   https://support.google.com/code/contact/billing_quota_increase.
3. **APIs** — Check: `gcloud services list --enabled --project <id>`.
   Configure: `gcloud services enable firestore.googleapis.com cloudfunctions.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com run.googleapis.com secretmanager.googleapis.com eventarc.googleapis.com identitytoolkit.googleapis.com iamcredentials.googleapis.com --project <id>` (+ `firebaseapphosting.googleapis.com` with `web-nextjs`).
4. **Firestore** — Check: `gcloud firestore databases list --project <id>`.
   Configure (confirm location): `gcloud firestore databases create --location <region> --project <id>`.
5. **Authentication** — Check: `curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: <id>" https://identitytoolkit.googleapis.com/admin/v2/projects/<id>/config`.
   - `CONFIGURATION_NOT_FOUND` → Auth isn't initialized. User: https://console.firebase.google.com/project/<id>/authentication
     → **Get started** (only this click; providers are set by Claude next).
   - Then Configure providers via API (same headers, `-X PATCH`, JSON body):
     anonymous: `.../config?updateMask=signIn.anonymous.enabled` with `{"signIn":{"anonymous":{"enabled":true}}}`;
     email: `updateMask=signIn.email.enabled,signIn.email.passwordRequired`;
     Apple (iOS-only, no Services ID needed): `POST .../projects/<id>/defaultSupportedIdpConfigs?idpId=apple.com`
     with `{"enabled":true,"clientId":"<bundle><suffix>"}`;
     Google: User enables it in the console (needs an OAuth consent screen).
   - Apple sign-in also needs the "Sign In with Apple" capability on the App ID: `expo-ios` sets
     `ios.usesAppleSignIn: true`, EAS syncs the capability on build.
6. **App registrations** — only for enabled modules. Check: `firebase apps:list -P <id>`.
   Configure: `expo-ios` → `firebase apps:create IOS "<Name>" --bundle-id <bundle><suffix> -P <id>`;
   `expo-android` → `firebase apps:create ANDROID "<Name>" --package-name <bundle><suffix> -P <id>`;
   `web-nextjs` or `expo` with JS SDK → `firebase apps:create WEB "<Name> web" -P <id>`.
   Suffixes per environment: see `${CLAUDE_PLUGIN_ROOT}/skills/environments/references/expo-eas.md`.

## Then (once)

7. **Functions package** — Check: `functions/package.json`.
   Configure: TypeScript package with `firebase-functions`, `firebase-admin`, `engines.node` = project LTS, region from decisions.
8. **Local config** — run the `environments` skill (`.firebaserc`, `firebase.json`, `functions/.env.<env>`).
   Emulator ports: check they're free first (`lsof -nP -iTCP:<port> -sTCP:LISTEN`); 8080 is often
   taken, so default Firestore to 8085. Firestore rules: deny by default, `users/{uid}` owned by `request.auth.uid`.
9. **Artifact cleanup policy** — after the first functions deploy to each environment:
   `firebase functions:artifacts:setpolicy --location <region> -P <env> --force` (deletes images older
   than 1 day). Without it, `firebase deploy --non-interactive` (CI) exits with an error even though
   the deploy succeeded. Before the first deploy the repo doesn't exist: record an open item.

## Done when

- Emulators: `firebase emulators:exec -P dev --only functions,firestore,auth "<curl health; anonymous signUp against :9099>"`
  returns the health JSON and a uid.
- Cloud: `firebase deploy --only functions,firestore -P dev` succeeds, the health URL responds,
  cleanup policy set. Protected environments: only on the user's explicit request.
