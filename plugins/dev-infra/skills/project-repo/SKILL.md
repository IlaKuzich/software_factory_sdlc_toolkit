---
name: project-repo
description: dev-infra core module. Sets up the project repository — create a new one, use the current directory, or clone a repo the user created — then the pnpm monorepo, .dev-infra/environments.yaml, .dev-infra/DEVINFRA.md decision record and the dev-infra block in CLAUDE.md. Use when starting a project or when the dev-infra files are missing.
---

# Module: project-repo

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.
File formats: `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/devinfra-template.md`.

**Requires:** workstation

## Decisions

Ask **Repository source** first; it determines which other decisions are needed.

- **Repository source** — detect before asking: is the current directory a git repo
  (`git rev-parse --show-toplevel`), does it have a GitHub remote (`gh repo view --json nameWithOwner,visibility,isEmpty`),
  is it empty apart from git/README/LICENSE? Then offer (recommend the one matching what was detected):
  - **Create new** — new directory, `git init`, new private GitHub repo created by Claude.
  - **Use current directory** — the user already created the repo (and/or code is here).
    Repo owner/name come from the remote; no `gh repo create`.
  - **Clone existing** — the user created the repo on GitHub; ask for `owner/name`, `gh repo clone` it.
- **Project slug** — lowercase, used for Firebase project IDs (and the repo name when creating new).
  For an existing repo, propose the repo name as the slug.
- **App display name.**
- **Bundle id / package base** — reverse domain the user controls (`com.<name>.<app>`).
  Irreversible once published to a store.
- **Environments** — default `dev, staging, prod`; protected: the highest one.
- **GitHub owner** (create new only) — personal account, or an organization (needed only to share
  self-hosted runners across repos; free at https://github.com/organizations/plan).
- **Node LTS major** for the project (must be a Firebase Functions runtime).

## Steps

1. **Repository** — by source:
   - *Create new*: Check: target dir doesn't exist or is empty. Configure: `mkdir <dir> && git init -b main`.
   - *Use current directory*: Check: it's a git repo; note its remote and default branch. If it has no
     remote, ask whether to create one in step 5 or leave it local.
   - *Clone existing*: Check: `gh repo view <owner/name>`. Configure: `gh repo clone <owner/name> <dir>`.
   For existing repos: if `visibility` is PUBLIC, warn (self-hosted runners would run fork PR code;
   secrets in logs are public) and record the user's choice. Existing code is never overwritten:
   list conflicting files and merge (e.g. add workspace entries to an existing `package.json`).
2. **Monorepo** — Check: `pnpm-workspace.yaml`.
   Configure: `pnpm-workspace.yaml` (`apps/*`, `packages/*`, `functions`); root `package.json`
   (`private: true`, `packageManager: pnpm@<version>`, scripts `lint`/`typecheck`/`test` as `pnpm -r --if-present …`);
   `.nvmrc` with the Node LTS major; `.gitignore` (node_modules, .env.local, .expo, .next, dist, *.log).
   pnpm ≥ 11 fails installs when a dependency has build scripts not listed in `allowBuilds`
   (`pnpm-workspace.yaml`, map of `package: true|false`). On `ERR_PNPM_IGNORED_BUILDS`, look up what
   each script does, set true only if needed, and record it as a decision. pnpm may add a placeholder
   `allowBuilds:` block itself — edit that one, never add a second key.
   If the repo already uses another package manager or layout, stop and ask before converting.
   Apps are created by their platform modules, not here.
3. **dev-infra files** — Check: `.dev-infra/environments.yaml`, `.dev-infra/DEVINFRA.md`, CLAUDE.md block.
   Configure: environments.yaml from `${CLAUDE_PLUGIN_ROOT}/skills/environments/templates/environments.yaml`
   filled with the decisions (drop sections of modules not selected); DEVINFRA.md with the module
   selection from bootstrap and the decisions made so far, including the repository source;
   CLAUDE.md managed block (append to an existing CLAUDE.md, never replace it).
   Tools now write version-specific agent rules to `AGENTS.md` (turbo at the root, Next.js in `apps/web`,
   Expo in `apps/mobile`); Claude Code reads only CLAUDE.md, so (ask once, record the decision) import them:
   `@AGENTS.md` line in the root managed block, and an app-level `CLAUDE.md` containing `@AGENTS.md` next to each
   app's AGENTS.md. Templates may also enable tool Claude plugins in an app-level `.claude/settings.json`
   (e.g. `expo@claude-plugins-official`): offer to move them to the root `.claude/settings.json`.
4. **Commit** — on the default branch for a fresh repo; for an existing repo with content, ask whether
   to commit on a branch (`chore/dev-infra-bootstrap`) and open a PR instead.
5. **GitHub remote** — Check: `gh repo view` from the project dir.
   - *Create new*: Configure (confirm; **private**, self-hosted runners run repo code):
     `gh repo create <owner>/<slug> --private --source . --push`.
   - *Use current / Clone*: `git push` (or the branch + `gh pr create` from step 4).
   Record: `ci.github_repo` in environments.yaml.

## Done when

`gh repo view` works, dev-infra files are on GitHub (default branch or an open PR).
