---
name: ci-cd
description: dev-infra service module. Set up or update GitHub Actions CI/CD for an Expo (iOS/Android) + Next.js + Firebase project — PR checks, per-environment Firebase deploys, mobile builds on self-hosted runners (Mac mini for iOS, Windows laptop for Android), and a scheduled runner health check. Also covers registering self-hosted runners via the GitHub API. Use when the user asks for CI, CD, GitHub Actions, workflows, pipelines, or to add/register a runner.
---

# Module: ci-cd

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.

**Requires:** project-repo. Installs only the parts for enabled modules (read `.dev-infra/DEVINFRA.md`):
`deploy.yml` needs `firebase` (and deploys `apphosting` only with `web-nextjs`);
`mobile-build.yml` jobs per `expo-ios` / `expo-android`; `runner-health.yml` needs `runners`.

Driven by the `ci:` and `environments:` sections of `.dev-infra/environments.yaml`
(see the `environments` skill; add the `ci:` block from its template if missing).

## What gets installed in the project

| Project file | Source (`${CLAUDE_PLUGIN_ROOT}/...`) | Purpose |
|---|---|---|
| `.github/workflows/ci.yml` | `skills/ci-cd/templates/workflows/ci.yml` | lint/typecheck/test on PRs (GitHub-hosted) |
| `.github/workflows/deploy.yml` | `skills/ci-cd/templates/workflows/deploy.yml` | Firebase deploy; main → `ci.deploy.on_push_main`, manual for others |
| `.github/workflows/mobile-build.yml` | `skills/ci-cd/templates/workflows/mobile-build.yml` | `eas build --local` on self-hosted runners |
| `.github/workflows/runner-health.yml` | `skills/ci-cd/templates/workflows/runner-health.yml` | API + on-machine runner checks every 6h |
| `.github/scripts/check_runners.py` | `scripts/check_runners.py` | runner registration/online/labels via API |
| `.github/scripts/runner_doctor.sh` | `scripts/runner_doctor.sh` | on-machine checks (macOS, Linux/WSL) |
| `.github/scripts/runner_doctor.ps1` | `scripts/runner_doctor.ps1` | on-machine checks (native Windows / Windows host) |

## Workflow

1. **Load the spec**; confirm `ci.github_repo` matches `gh repo view --json nameWithOwner`.
2. **Copy and adapt templates.** Merge with existing workflows rather than overwriting. Adapt:
   - package manager (`ci.package_manager`) and Node version;
   - `APP_DIR` and paths from `apps.*.path`; drop jobs for apps the project doesn't have;
   - `workflow_dispatch` environment options = spec environment names;
   - `runs-on` labels and `--expect NAME:labels` = `ci.runners[*]`;
   - a runner with `os: windows` can't run `eas build --local`: use the native Windows job
     from [references/runners.md](references/runners.md#native-windows-android-job), and
     run `runner_doctor.ps1` with `shell: pwsh` in `runner-health.yml`.
   - Bump action major versions if newer ones exist.
3. **Configure GitHub** with `gh` (show the commands, run after the user confirms):
   - GitHub Environments, one per spec environment:
     `gh api -X PUT repos/OWNER/REPO/environments/<env>`
   - Per-environment variables:
     `gh variable set EAS_PROFILE --env <env> --body <eas_profile>`,
     `GCP_WIF_PROVIDER` and `GCP_DEPLOY_SA` (see "Firebase auth" below).
   - Protected environments: suggest required reviewers / branch restrictions in
     repo Settings → Environments (availability on private repos depends on the GitHub plan).
4. **Secrets: the user sets the values, never you.** Tell them to run, in a separate terminal (each prompts for the value):
   - `gh secret set EXPO_TOKEN` (expo.dev → Access tokens; a robot user token is best)
   - `gh secret set RUNNER_ADMIN_TOKEN` (fine-grained PAT, this repo, Administration: read-only)
5. **Runners**: if `/dev-infra:runners` shows a runner isn't registered, walk the user through
   [references/runners.md](references/runners.md).
6. **Verify**: `actionlint` if installed; push and `gh run watch` the CI run.

## Done when

CI is green on main, and a dev deploy run succeeds (if `firebase` is enabled).

## Firebase auth (Workload Identity Federation, no JSON keys)

Per Firebase project (= environment), once, by the user or with their confirmation:

```sh
P=<firebase_project>; REPO=OWNER/REPO
gcloud iam service-accounts create github-deploy --project $P
# roles: Firebase Admin, Cloud Functions Admin, Service Account User, Artifact Registry Writer,
#        Cloud Build Editor, Firebase App Hosting Admin (grant with add-iam-policy-binding)
gcloud iam workload-identity-pools create github --location global --project $P
gcloud iam workload-identity-pools providers create-oidc github --location global \
  --workload-identity-pool github --project $P \
  --issuer-uri https://token.actions.githubusercontent.com \
  --attribute-mapping google.subject=assertion.sub,attribute.repository=assertion.repository \
  --attribute-condition "assertion.repository=='$REPO'"
# allow the repo to impersonate the SA (roles/iam.workloadIdentityUser on principalSet .../attribute.repository/$REPO)
```

Then set `GCP_WIF_PROVIDER` (`projects/<number>/locations/global/workloadIdentityPools/github/providers/github`)
and `GCP_DEPLOY_SA` (`github-deploy@<project>.iam.gserviceaccount.com`) on that GitHub Environment.

If App Hosting is connected to GitHub for automatic rollouts, either disable automatic rollouts
(CI deploys it) or remove `apphosting` from `--only` in `deploy.yml`, to avoid double deploys.

## Security

Self-hosted runners execute workflow code from the repo on your machines. Keep the repo
**private**; on a public repo, a fork PR could run code on the Mac mini.
