---
name: ci-cd
description: dev-infra service module. Set up or update GitHub Actions CI/CD for an Expo (iOS/Android) + Next.js + Firebase project — CI on PRs (Turborepo lint/typecheck/test/build + web E2E), deploys that run only after green CI (dev) or manually (protected environments) with post-deploy smoke tests, Workload Identity Federation per environment, GitHub Environments, and optional mobile builds on self-hosted runners. Use when the user asks for CI, CD, GitHub Actions, workflows, pipelines, or to add/register a runner.
---

# Module: ci-cd

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.

**Requires:** project-repo. Installs only the parts for enabled modules (read `.dev-infra/DEVINFRA.md`):
`deploy.yml` needs `firebase` (deploys `apphosting` only with `web-nextjs`; web smoke only with `e2e-playwright`);
CI's Playwright steps need `e2e-playwright`; `mobile-build.yml` needs `expo-ios`/`expo-android` **and** a decision
to build in CI; `runner-health.yml` needs `runners`.

Driven by the `ci:` and `environments:` sections of `.dev-infra/environments.yaml`.

## Decisions

- **Mobile in CI** — recommend *not yet* until native builds have somewhere to run:
  A) no mobile builds in CI (typecheck/lint only; native builds local with `eas build --local`) — no `EXPO_TOKEN`;
  B) EAS Update (OTA) of the JS bundle to the environment's channel on each deploy — needs `expo-updates`, `EXPO_TOKEN`;
  C) native builds only when the native fingerprint changes (`expo-fingerprint`), on the Mac mini runner (`runners`)
  or EAS cloud — needs `EXPO_TOKEN`. Record the choice; B/C go to Open items if deferred.
- **Protected environments** — deploy only by manual dispatch. Required reviewers on GitHub Environments need a
  paid plan for private repos (API returns 422 on Free): fall back to a deployment branch policy (`main` only) +
  the plugin's deploy guard hook, and record it.

## What gets installed in the project

| Project file | Source (`${CLAUDE_PLUGIN_ROOT}/...`) | Purpose |
|---|---|---|
| `.github/workflows/ci.yml` | `skills/ci-cd/templates/workflows/ci.yml` | PR + main: turbo lint/typecheck/test/build, web E2E |
| `.github/workflows/deploy.yml` | `skills/ci-cd/templates/workflows/deploy.yml` | after green CI on main → `ci.deploy.on_push_main`; manual for others; smoke tests |
| `.github/workflows/mobile-build.yml` | `skills/ci-cd/templates/workflows/mobile-build.yml` | (option C) `eas build --local` on self-hosted runners |
| `.github/workflows/runner-health.yml` | `skills/ci-cd/templates/workflows/runner-health.yml` | (`runners`) API + on-machine runner checks every 6h |
| `.github/scripts/*` | `scripts/check_runners.py`, `runner_doctor.sh`, `runner_doctor.ps1` | (`runners`) |
| `.github/actionlint.yaml` | `skills/ci-cd/templates/actionlint.yaml` | (`runners`) custom runner labels for actionlint |

## Steps

1. **Local CI parity first** — the workflows run on a clean checkout, where generated files (`.next/types`,
   `expo-env.d.ts`) and interactive installers don't exist. Before pushing workflows, run the exact CI sequence
   in a **clean clone** (`git clone <repo> <scratch> && cd <scratch> && CI=1 pnpm install --frozen-lockfile &&
   CI=1 pnpm lint && CI=1 pnpm typecheck && CI=1 pnpm test && CI=1 pnpm build && CI=1 pnpm --filter web e2e`,
   each with `</dev/null`). Known fixes:
   - Next.js global types (`LayoutProps`, `PageProps`) come from `next typegen`: web `typecheck` = `next typegen && tsc --noEmit`.
   - Expo templates ship a `lint` script without ESLint: `npx expo install eslint eslint-config-expo -- --save-dev`
     + `eslint.config.js` (`eslint-config-expo/flat`); fix template lint errors properly (e.g. setState-in-effect
     hydration hook → `useSyncExternalStore`), don't disable rules.
   - `next build`/`next start` don't read `.env.development`: put default (dev, public) web config in `apps/web/.env`;
     App Hosting env vars override it per environment.
2. **Copy and adapt templates.** Merge with existing workflows rather than overwriting. Adapt: Node from `.nvmrc`;
   app paths; `workflow_dispatch` environment options = spec environment names; drop steps for disabled modules;
   `runs-on` labels = `ci.runners[*]`. Check current action majors (`gh api repos/<action>/releases/latest --jq .tag_name`)
   and use them. Lint with `actionlint` (`brew install actionlint`, ask first).
3. **Workload Identity Federation** (per environment = per Firebase project; confirm first):
   ```sh
   P=<firebase_project>; ENV=<env>; REPO=<owner/repo>; N=$(gcloud projects describe $P --format='value(projectNumber)')
   SA=github-deploy@$P.iam.gserviceaccount.com
   gcloud iam service-accounts create github-deploy --project $P --display-name "GitHub Actions deploy ($ENV)"
   for r in firebase.admin cloudfunctions.admin run.admin iam.serviceAccountUser artifactregistry.admin \
            cloudbuild.builds.editor serviceusage.serviceUsageConsumer storage.admin firebaseapphosting.admin; do
     gcloud projects add-iam-policy-binding $P --member serviceAccount:$SA --role roles/$r --condition=None --quiet; done
   gcloud iam workload-identity-pools create github --location global --project $P
   gcloud iam workload-identity-pools providers create-oidc github --location global --workload-identity-pool github \
     --project $P --issuer-uri https://token.actions.githubusercontent.com \
     --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.environment=assertion.environment" \
     --attribute-condition "assertion.repository=='$REPO'"
   # Only jobs running in the GitHub Environment of the same name may impersonate this SA:
   gcloud iam service-accounts add-iam-policy-binding $SA --project $P --role roles/iam.workloadIdentityUser \
     --member "principalSet://iam.googleapis.com/projects/$N/locations/global/workloadIdentityPools/github/attribute.environment/$ENV"
   ```
   (`artifactregistry.admin` lets `deploy --force` set the image cleanup policy; `storage.admin` lets App Hosting
   create its source bucket on the first deploy.)
4. **GitHub Environments + variables** (one per spec environment):
   `gh api -X PUT repos/<repo>/environments/<env>`; variables `GCP_WIF_PROVIDER`
   (`projects/<N>/locations/global/workloadIdentityPools/github/providers/github`), `GCP_DEPLOY_SA`, `WEB_URL`
   (App Hosting backend URL), `FUNCTIONS_URL` (`https://<region>-<project>.cloudfunctions.net`), and `EAS_PROFILE`
   if mobile is built in CI. Protected environments: try required reviewers
   (`gh api -X PUT .../environments/<env> --input <json with reviewers>`); on 422 use
   `{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}` +
   `gh api -X POST .../environments/<env>/deployment-branch-policies -f name=main -f type=branch`.
5. **Secrets** — only those a workflow actually uses (`EXPO_TOKEN` for options B/C, `RUNNER_ADMIN_TOKEN` for
   `runners`). The user sets them in a separate terminal (`gh secret set NAME --repo <repo>` prompts for the value).
6. **Push and watch** — `gh run watch <id> --exit-status`. A deploy run takes longer than a 10-minute foreground
   command limit: watch it in the background. On failure: `gh run view <id> --log-failed`.

## Done when

CI is green on main, the automatic dev deploy (including smoke tests) is green, and a manual dispatch to a
protected environment is possible (run it only when the user asks).

## Notes

- Deploy is triggered by `workflow_run` of CI on main and checks out `workflow_run.head_sha`, so it ships exactly
  the commit CI tested; a failed CI never deploys.
- `firebase deploy --force` in CI: functions removed from source are deleted, and the image cleanup policy is
  set on the first deploy (without it a successful deploy still exits non-zero). Record as a decision.
- If App Hosting is connected to GitHub for automatic rollouts, disable them (CI deploys) to avoid double deploys.
- Self-hosted runners execute repo code on your machines: keep the repo **private**.
