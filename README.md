# sdlc-toolkit

Personal Claude Code plugin marketplace for the Software Factory.

## Plugins

| Plugin | What it does |
|---|---|
| [`dev-infra`](plugins/dev-infra) | Deploy environments (dev/staging/prod), GitHub Actions CI/CD and self-hosted runner checks for Expo iOS/Android + Next.js (Firebase App Hosting) + Firebase, driven by `.dev-infra/environments.yaml`. Asks before deploying to protected environments. |

## Install

From a local clone:

```sh
claude plugin marketplace add /path/to/software_factory_sdlc_toolkit
claude plugin install dev-infra@sdlc-toolkit
```

Or enable it per project in the project's committed `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "sdlc-toolkit": {
      "source": { "source": "directory", "path": "/path/to/software_factory_sdlc_toolkit" }
    }
  },
  "enabledPlugins": { "dev-infra@sdlc-toolkit": true }
}
```

Once the repo is pushed to GitHub, switch the source to
`{ "source": "github", "repo": "<owner>/<repo>" }` so it works on any machine.

## Usage

`dev-infra` is modular: one skill per platform/service, catalogued in
[`plugins/dev-infra/modules.yaml`](plugins/dev-infra/modules.yaml). In a project run
`/dev-infra:bootstrap`: it asks which modules the project uses, records the choice and every
decision in `.dev-infra/DEVINFRA.md` (linked from a managed block in `CLAUDE.md`), and runs the
modules in dependency order. Each step checks first, configures what it can, and asks you for the
manual parts (sign-ups, consoles, logins). Any module can also be run alone, e.g.
`/dev-infra:expo-android` to add Android later.

| Module | Kind | Sets up |
|---|---|---|
| `workstation` | core | gh, gcloud, firebase, node/pnpm + logins |
| `project-repo` | core | pnpm monorepo, private GitHub repo, `.dev-infra/` files, CLAUDE.md block |
| `firebase` | platform | project per env, billing, Firestore, Auth, Functions, app registrations |
| `expo` | platform | Expo app, EAS project, variants, EAS env vars |
| `expo-ios` | platform | Apple Developer, Xcode toolchain, signing, first build |
| `expo-android` | platform | JDK/SDK, keystore, optional Google Play |
| `web-nextjs` | platform | thin Next.js on Firebase App Hosting |
| `ci-cd` | service | GitHub Actions: CI, deploys, mobile builds, Environments/secrets |
| `runners` | service | self-hosted runners (Mac mini, Windows/WSL2) + health checks |
| `e2e-playwright` | service | Playwright web E2E: local, PR checks, post-deploy smoke |
| `e2e-maestro` | service (beta) | Maestro E2E flows, locally and on runners |
| `artifacts` | service (planned) | shared packages / images storage |

Utility skills:

| Skill | Does |
|---|---|
| `/dev-infra:verify` | Read-only check of all enabled modules: config vs spec, cloud state (drift), live smoke tests. Script: `scripts/verify_project.py` (also usable in CI with `--ci --json`) |
| `/dev-infra:demo` | One button on each client (Expo, web) → Firebase callable `demoEcho` → fixed response; proves the wiring end to end. Removable (`/dev-infra:demo remove`) |
| `/dev-infra:environments` | Syncs per-environment config files from `.dev-infra/environments.yaml` |

The runner doctor scripts also work standalone on a runner machine:
`bash plugins/dev-infra/scripts/runner_doctor.sh --platform ios` (macOS / WSL2) or
`pwsh plugins/dev-infra/scripts/runner_doctor.ps1` (Windows).

## Adding a module

Write `plugins/dev-infra/skills/<id>/SKILL.md` following
[module-contract.md](plugins/dev-infra/skills/bootstrap/references/module-contract.md), add it to
`modules.yaml`, bump the version.

## Adding a plugin

1. Create `plugins/<name>/.claude-plugin/plugin.json` plus `skills/`, `hooks/`, etc.
2. Add an entry to `.claude-plugin/marketplace.json`.
3. Validate: `claude plugin validate .` and `claude plugin validate plugins/<name>`.
4. Bump `version` in both manifests when you change a plugin, so installs pick up the update.
