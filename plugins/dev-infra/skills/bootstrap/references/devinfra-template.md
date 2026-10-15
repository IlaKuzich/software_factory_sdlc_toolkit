# Project files written by dev-infra

## `.dev-infra/DEVINFRA.md` (decision record, human-first)

```markdown
# Dev Infra

Managed with the `dev-infra` plugin. This file records **which parts of dev-infra this project
uses and why**. Config values live in [environments.yaml](environments.yaml).
Re-run `/dev-infra:bootstrap` to resume setup or add a module.

## Modules

| Module | Status | Notes |
|---|---|---|
| workstation | done | |
| project-repo | done | pnpm monorepo, private repo owner/app |
| firebase | done | dev / staging / prod |
| expo | done | |
| expo-ios | done | Apple team ABCDE12345 |
| expo-android | in progress | Play Console deferred |
| web-nextjs | not used | no web app yet |
| ci-cd | pending | |
| runners | pending | |
| e2e-maestro | pending | |
| artifacts | not used | workspace packages are enough for now |

Statuses: `pending` · `in progress` · `done` · `deferred: <why>` · `not used`.

## Decisions

### 2026-10-09 · Firestore location: `eur3` (firebase)
Users are in the EU; multi-region for availability. **Irreversible.**

### 2026-10-09 · Android runner in WSL2, not native Windows (runners)
`eas build --local` needs Linux/macOS.

## Open items

- [ ] expo-android: register Google Play Console ~1 month before first Play release (14-day closed test)
```

Rules: one `###` per decision, newest last, format `date · title: choice (module)` + a 1–3 line why.
Never rewrite an old decision; supersede it with a new entry that says what it replaces.

## `CLAUDE.md` managed block

Create CLAUDE.md if missing; otherwise insert/replace only between the markers:

```markdown
<!-- dev-infra:begin (managed by the dev-infra plugin; edit .dev-infra/DEVINFRA.md instead) -->
## Dev infra

Active modules: firebase, expo, expo-ios, expo-android, ci-cd, runners.
Decisions and setup status: [.dev-infra/DEVINFRA.md](.dev-infra/DEVINFRA.md) — read it before
changing infra, CI, environments or build config. Config: `.dev-infra/environments.yaml`.
Environments: dev, staging, prod (protected: prod — deploy only on explicit request).
<!-- dev-infra:end -->
```

Keep the block short: it's loaded into every session. Details belong in DEVINFRA.md.
