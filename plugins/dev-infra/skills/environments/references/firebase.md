# Firebase: projects, aliases, Functions config

One Firebase project per environment. This isolates data, auth users, quotas and billing.

## `.firebaserc`

One alias per spec environment, aliased by the environment name:

```json
{
  "projects": {
    "default": "myapp-dev",
    "dev": "myapp-dev",
    "staging": "myapp-staging",
    "prod": "myapp-prod"
  }
}
```

`default` points at the first non-protected environment so a bare `firebase deploy` can never hit prod.

## Functions parameters

- Non-secret config: `functions/.env` (shared defaults) plus `functions/.env.<alias>` per
  environment. Firebase loads the file matching the alias or project id on deploy.
  Read values in code with `defineString` / `defineInt` from `firebase-functions/params`.
- Secrets: listed under `apps.functions.secrets` in the spec. Declare them in code with
  `defineSecret("NAME")` and bind them to the function (`{ secrets: [name] }`).
  Values are set per project by the user: `firebase functions:secrets:set NAME -P <env>`.
- Add `functions/.env.local` to `.gitignore` (emulator overrides); the `.env.<alias>`
  files are committed since they hold no secrets.

## Deploy commands

Always pass the alias explicitly: `firebase deploy --only functions -P staging`.

## Emulators

Local development uses the emulator suite against the `dev` alias:
`firebase emulators:start -P dev`. Client apps detect emulator mode via an env flag
(`EXPO_PUBLIC_USE_EMULATORS`, `NEXT_PUBLIC_USE_EMULATORS`) and call `connect*Emulator`.
