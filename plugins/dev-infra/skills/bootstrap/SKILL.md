---
name: bootstrap
description: Entry point for dev-infra. Chooses which dev-infra modules a project uses (Firebase, Expo iOS/Android, Next.js web, CI/CD, self-hosted runners, Maestro E2E, …), records the choice in .dev-infra/DEVINFRA.md linked from CLAUDE.md, and runs each module's setup in dependency order — from nothing, or resuming a half-finished setup. Use when starting a new project, adding/removing a platform or service, or asking "what's left to set up?".
---

# Bootstrap (module orchestrator)

dev-infra is a set of **modules**, one skill each, listed in `${CLAUDE_PLUGIN_ROOT}/modules.yaml`.
This skill only selects, orders and tracks them; each module does its own setup.

- Module rules: [references/module-contract.md](references/module-contract.md)
- How every step runs (check → configure → ask the user): [references/step-protocol.md](references/step-protocol.md)
- Files written into the project: [references/devinfra-template.md](references/devinfra-template.md)

## 1. Load state

- Read `${CLAUDE_PLUGIN_ROOT}/modules.yaml`.
- If the project has `.dev-infra/DEVINFRA.md`, read the Modules table: this is a resume or a change.
- Otherwise it's a fresh start (there may be no project directory yet).

## 2. Choose modules (fresh start, or when the user wants to add/remove)

Ask with AskUserQuestion (multi-select), grouped by `kind`:
- `core` modules are always on; just state them.
- `platform`: which app targets/backends (iOS, Android, web, Firebase…).
- `service`: CI/CD, runners, E2E, …
- `planned` modules: show as "planned, not available yet"; if chosen, record as `pending` with a note.

Add missing `requires` automatically and say which were added and why.
Never silently drop a module that's `done`; switching one to `not used` is a recorded decision.

## 3. Record

If DEVINFRA.md exists, update its table and add a decision entry for the change
("Modules: added e2e-maestro"). Before `project-repo` has run, keep the selection in
the conversation; `project-repo` creates DEVINFRA.md and the CLAUDE.md block from it.

## 4. Run

Topologically order the selected modules by `requires`, core first. For each module not `done`:
announce it (`module k/N: <id> — <summary>`), invoke the module skill `dev-infra:<id>`,
and follow it to its "Done when". Long external waits: mark `deferred: <why>` and continue with
modules that don't depend on it.

## 5. Report

End with the Modules table, open items, and the next action for the user.
