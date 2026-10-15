# Next.js on Firebase App Hosting

The web app is a thin SSR layer: rendering and calling Firebase. Business logic belongs in
Functions/Firestore rules, so web env config should stay small.

## Layout

Each Firebase project (one per environment) has its own App Hosting backend
(`apps.web.app_hosting_backend`). In the console, set each backend's **environment name**
to the spec environment name; App Hosting then merges `apphosting.<env>.yaml` over `apphosting.yaml`.

Place the files in the web app root (`apps.web.path`).

`apphosting.yaml` (shared defaults):

```yaml
runConfig:
  minInstances: 0
  maxInstances: 4
env:
  - variable: NEXT_PUBLIC_APP_ENV
    value: dev
    availability: [BUILD, RUNTIME]
```

`apphosting.prod.yaml` (overrides for one environment):

```yaml
runConfig:
  minInstances: 1
env:
  - variable: NEXT_PUBLIC_APP_ENV
    value: prod
    availability: [BUILD, RUNTIME]
  - variable: SOME_SERVER_SECRET
    secret: some-server-secret   # Secret Manager name; set via `firebase apphosting:secrets:set`
```

App Hosting injects the Firebase web config automatically (`FIREBASE_WEBAPP_CONFIG`), so
`initializeApp()` with no arguments works on the server; don't duplicate it per environment.

## Local development

`.env.local` (gitignored) for local overrides; `.env.development` for committed, non-secret
defaults pointing at the `dev` project or emulators.

## Deploy

Rollouts are triggered by pushes to the backend's live branch, or manually:
`firebase deploy --only apphosting -P <env>`.
