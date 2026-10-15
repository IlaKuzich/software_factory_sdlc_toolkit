---
name: demo
description: End-to-end demo that proves the dev-infra wiring works — one screen with one button on each enabled client (Expo app, Next.js web) that calls a Firebase callable function and shows its fixed response. Exercises per-environment client config, anonymous auth, the functions region and deploys. Use after setting up firebase + a client module, to check a new environment, or to remove the demo (`remove`).
---

# Demo: one button → callable function → fixed response

Not a module: it consumes `firebase` plus whichever of `expo`, `web-nextjs` are `done`.
All demo code lives in files named `demo*` with a `dev-infra:demo` marker comment so it can be removed cleanly.
Firestore is deliberately not used (that's covered by `verify`).

## Contract

- **Function** `demoEcho` (callable, region = `firebase.functions_region`), no input, returns exactly:
  `{ "message": "Hello from <App name>", "env": "<APP_ENV>", "authenticated": <bool> }`.
- **Client**: button `testID/data-testid="demo-button"`, result `testID/data-testid="demo-result"`
  showing `message` and `env`. Before calling: `signInAnonymously` if `anonymous` is in
  `firebase.auth_providers` (then `authenticated` must be `true`).
- **Emulators**: if `EXPO_PUBLIC_USE_EMULATORS` / `NEXT_PUBLIC_USE_EMULATORS` is `1`, connect
  Functions (5001) and Auth (9099) emulators.

## Steps

1. **Function** — Check: `functions/src/demo.ts` exists and is exported from `functions/src/index.ts`.
   Configure:
   ```ts
   // functions/src/demo.ts — dev-infra:demo
   import { onCall } from "firebase-functions/v2/https";
   import { defineString } from "firebase-functions/params";

   const appEnv = defineString("APP_ENV");

   export const demoEcho = onCall((request) => ({
     message: "Hello from <App name>",
     env: appEnv.value(),
     authenticated: Boolean(request.auth),
   }));
   ```
   plus `export { demoEcho } from "./demo.js"; // dev-infra:demo` in index.ts.
   Verify on emulators, then deploy to dev: `firebase deploy --only functions:demoEcho -P dev`.
   Smoke (no client needed):
   `curl -s -X POST -H 'Content-Type: application/json' -d '{"data":{}}' https://<region>-<dev id>.cloudfunctions.net/demoEcho`
   → `{"result":{"message":"Hello from …","env":"dev","authenticated":false}}`.
2. **Expo screen** (if `expo` done) — route file in the router dir (`src/app/demo.tsx` in SDK 57 templates,
   `app/demo.tsx` in older ones): `npx expo install firebase`; Firebase JS SDK initialized from
   `EXPO_PUBLIC_FIREBASE_*` (each referenced literally — they're inlined at build time), `getFunctions(app, region)`,
   `signInAnonymously`, `httpsCallable(functions, "demoEcho")`. JS-only: no native rebuild needed.
   Make it reachable: if the layout uses tabs (`NativeTabs` in SDK 57's template), add a `Demo` tab trigger
   marked `dev-infra:demo`; otherwise a marked link from the home screen.
   Verify: if `e2e-maestro` is enabled, add `apps/mobile/.maestro/demo.yaml` following that module's dev-client
   flow pattern (connect to Metro → tap `Demo` with retry → tap `demo-button` → wait for `demo-result` →
   assert `Hello from <App name>` and `.*authenticated: true.*`) plus an `e2e:demo` script, and run it;
   otherwise ask the user to tap the button and report.
3. **Web page** (if `web-nextjs` done) — `apps/web/src/app/demo/page.tsx` (client component), same call.
   Firebase config: `NEXT_PUBLIC_FIREBASE_*` in `apphosting.<env>.yaml` (public values), or App Hosting
   auto-init (requires `allowBuilds: "@firebase/util": true` in pnpm-workspace.yaml).
   Verify: if `e2e-playwright` is enabled, add `apps/web/e2e/demo.spec.ts` (goto `/demo` → click `demo-button` →
   `demo-result` contains `Hello from <App name>`, `env: ${E2E_EXPECT_ENV}`, `authenticated: true`) and run it locally
   and with `E2E_BASE_URL` against the deployed backend; otherwise ask the user to open `/demo` and click.
4. **Per environment** — repeat the deploy + smoke for other environments only on the user's request
   (protected environments need explicit confirmation).
5. **Record** in DEVINFRA.md Open items: `Demo installed (<platforms>); remove with /dev-infra:demo remove`.

## Remove

Delete files containing `dev-infra:demo` (`functions/src/demo.ts`, `apps/mobile/app/demo.tsx`,
`apps/mobile/.maestro/demo.yaml`, `apps/web/src/app/demo/`), remove marked lines from index.ts and the home
screen, `firebase functions:delete demoEcho --region <region> -P <env> --force` per environment (ask first),
and update DEVINFRA.md.
