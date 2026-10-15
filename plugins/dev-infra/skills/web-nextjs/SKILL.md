---
name: web-nextjs
description: dev-infra platform module. Thin Next.js web app (SSR first, minimal business logic) on Firebase App Hosting — app scaffold in apps/web, one App Hosting backend per environment, per-environment apphosting yaml. Use when adding the web app or when App Hosting setup is incomplete.
---

# Module: web-nextjs

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.
Config conventions: `${CLAUDE_PLUGIN_ROOT}/skills/environments/references/nextjs-app-hosting.md`.

**Requires:** project-repo, firebase

## Decisions

- **UI kit / styling** — none · Tailwind v4 · a component library. Check the library's peer deps first
  (`npm view <pkg> peerDependencies`): e.g. HeroUI v3 (`@heroui/react`) requires Tailwind v4, so choosing it
  means `--tailwind` plus the library. Installing the library itself may be deferred to app architecture;
  record it as a decision either way (also whether its MCP server / agent skills are wanted).
- **Rollouts** — from CI (`ci-cd` deploys with `firebase deploy --only apphosting`; recommended,
  keeps deploy order under one pipeline) or App Hosting's GitHub auto-rollouts.

## Steps

0. **Monorepo tooling** — App Hosting only recognizes monorepos built with **Turborepo or Nx**; plain pnpm
   workspaces fail with `fah/missing-lock-file` (it looks for a lock file in `rootDir`). Check: `turbo.json` at the
   root. Configure: `pnpm add -Dw turbo`; `turbo.json` tasks `build` (`dependsOn: ["^build"]`, outputs
   `.next/**`, `!.next/cache/**`, `lib/**`, `dist/**`, and **`env: ["NEXT_PUBLIC_*", "EXPO_PUBLIC_*", "APP_VARIANT"]`** —
   Turbo 2 strips undeclared env vars and would cache builds across environments), `typecheck`, `lint`, `test`;
   root scripts `turbo run <task>`; `.turbo/` in .gitignore. Turbo writes a root `AGENTS.md` when it detects an agent: keep it.
1. **App** — Check: `apps/web/package.json`.
   Configure (confirm): `npx create-next-app@<version> apps/web --ts --app --eslint --src-dir --import-alias "@/*" --use-pnpm --skip-install --disable-git --yes [--tailwind]`.
   Then: **delete the generated `apps/web/pnpm-workspace.yaml`** (a nested workspace file splits the monorepo) after
   moving its `allowBuilds` entries into the root one; drop `packageManager` from the app's package.json; add
   `"engines": {"node": "<LTS>.x"}` (otherwise App Hosting builds with its default Node); add
   `"typecheck": "next typegen && tsc --noEmit"` (global `LayoutProps`/`PageProps` types are generated; a clean CI
   checkout has no `.next/types`). Default public dev config goes in `apps/web/.env` (read by dev, build and start;
   App Hosting env vars override it): the template ignores `.env*`, so add `!.env`.
   If `pnpm peers check` reports `@types/react` mismatches, pin the web app's `@types/react` to match `@types/react-dom`;
   don't override versions Expo pins in the mobile app.
   Add `firebase` (client) and `firebase-admin` (server) deps.
   App Hosting's no-argument `initializeApp()` relies on the `@firebase/util` postinstall script:
   either set `allowBuilds: "@firebase/util": true` in pnpm-workspace.yaml (record as a decision,
   superseding an earlier `false`), or pass explicit `NEXT_PUBLIC_FIREBASE_*` config.
2. **Backend per environment** — Check: `firebase apphosting:backends:list -P <id>`.
   Region: App Hosting has its own region list (often not the Functions region). List it:
   `curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: <id>" https://firebaseapphosting.googleapis.com/v1beta/projects/<id>/locations`
   (EU: only `europe-west4` as of 2026-10). Record the region as a decision.
   Configure (confirm): `firebase apphosting:backends:create -P <id> --backend <backend> --primary-region <region> --app <webAppId> --root-dir apps/web --non-interactive`.
   With `--non-interactive` no GitHub repo is connected (CI/local-source rollouts).
3. **Environment name** — Configure via API (no console click):
   `curl -X PATCH -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: <id>" -H "Content-Type: application/json" "https://firebaseapphosting.googleapis.com/v1beta/projects/<id>/locations/<region>/backends/<backend>?updateMask=environment" -d '{"environment":"<env>"}'`.
   Check: GET the backend → `environment` equals `<env>`.
4. **Config files** — run the `environments` skill: `apps/web/apphosting.yaml` (runConfig, shared env),
   `apps/web/apphosting.<env>.yaml` (`NEXT_PUBLIC_FIREBASE_*` from `firebase apps:sdkconfig WEB`, `NEXT_PUBLIC_APP_ENV`,
   availability BUILD+RUNTIME), `firebase.json` `"apphosting": [{"backendId": "<backend>", "rootDir": "apps/web", "ignore": [...]}]`.
   `firebase deploy --only apphosting` uploads the whole repo (lock file + workspaces) and builds `rootDir`.
   On a failed rollout read the build log: `gcloud builds log <build-id> --region <region> --project <id>`.

## Done when

`firebase deploy --only apphosting -P dev` succeeds and the backend URL
(`firebase apphosting:backends:get <backend> -P <dev id>`) serves the page.
