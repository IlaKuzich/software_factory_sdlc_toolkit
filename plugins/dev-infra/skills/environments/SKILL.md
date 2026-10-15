---
name: environments
description: dev-infra utility used by the platform modules. Set up, extend or audit deploy environments (dev/staging/prod) for a project built on Expo (iOS/Android), Next.js on Firebase App Hosting, and Firebase (Functions, Firestore, Auth). Use when the user wants to initialize environments, add a new environment, wire per-environment config/secrets, or check that environment config is consistent across .firebaserc, eas.json, app.config, apphosting.*.yaml and functions/.env.*.
---

# Deploy environments

The project's environments are defined in ONE spec file: `.dev-infra/environments.yaml`.
Every per-tool config file is derived from it. Your job is to keep the two in sync.

## Workflow

1. **Load the spec.** Read `.dev-infra/environments.yaml` in the project root.
   - If it is missing, copy `${CLAUDE_PLUGIN_ROOT}/skills/environments/templates/environments.yaml`,
     then ask the user for: app name, bundle id, Firebase project id per environment,
     and which apps exist (mobile / web / functions). Remove apps the project doesn't have.
2. **Detect what exists.** Only handle targets whose module is enabled in `.dev-infra/DEVINFRA.md`.
   Check each app path from the spec and the files listed below.
   Do not create an app that doesn't exist yet; just report that its env wiring is pending.
3. **Plan, then apply.** For each target, compute the desired state from the spec and
   show the user a short summary of files to create/change. Apply after confirmation.
   Edits must be idempotent: merge into existing files, never clobber unrelated keys.
4. **Report** the manual steps that can't be done from files (see "Manual steps").

Read only the reference for the targets that exist:

| Target | Files | Reference |
|---|---|---|
| Firebase projects + Functions | `.firebaserc`, `firebase.json`, `functions/.env.<alias>` | [references/firebase.md](references/firebase.md) |
| Expo mobile (iOS/Android) | `eas.json`, `app.config.ts` | [references/expo-eas.md](references/expo-eas.md) |
| Next.js web | `apphosting.yaml`, `apphosting.<env>.yaml` | [references/nextjs-app-hosting.md](references/nextjs-app-hosting.md) |

## Rules

- **No secrets in files.** Secrets go to Cloud Secret Manager (Functions, App Hosting) or
  EAS environment variables with `secret` visibility. Files only reference secret names.
- `EXPO_PUBLIC_*` and `NEXT_PUBLIC_*` values are shipped to clients: only public config
  (Firebase web config, API base URLs) may use them.
- Environment names in the spec are the canonical names; use them as Firebase aliases
  and App Hosting environment names so `firebase use <env>` and logs line up.
- Environments listed in `protected_environments` must never be deployed to without the
  user explicitly asking in this conversation. The plugin's hook also enforces a prompt.

## Adding an environment

Add it to `environments:` in the spec, then re-run this workflow: it adds the alias to
`.firebaserc`, an `eas.json` profile, an `apphosting.<env>.yaml`, and `functions/.env.<env>`.

## Manual steps (report, don't attempt silently)

- Creating Firebase projects and enabling billing (Blaze is required for Functions and App Hosting).
- Creating the App Hosting backend per Firebase project and setting its environment name.
- `eas init` / linking the Expo project, and creating EAS env vars and secrets.
- Setting secret values (`firebase functions:secrets:set`, `firebase apphosting:secrets:set`).
