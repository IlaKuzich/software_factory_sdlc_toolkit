---
name: verify
description: Read-only health check of a dev-infra project — verifies that every enabled module is configured correctly on three levels (config files vs spec, cloud state in GitHub/Google Cloud/Firebase, live smoke tests) and reports drift with fixes. Use when the user asks whether everything is set up correctly, after finishing a module, after manual console changes, or before a release.
---

# Verify

Changes nothing. Enabled modules come from `.dev-infra/DEVINFRA.md` (`done` / `in progress`);
`pending` and `not used` modules are listed as skipped.

## 1. Deterministic checks (script)

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/verify_project.py" --project <project root> [--level config|cloud|smoke]
```

- `config` — repo files agree with `.dev-infra/environments.yaml` (aliases, runtime, env files, CLAUDE.md block, workflows).
- `cloud` — read-only API calls: repo private, billing, APIs, Firestore location, Auth providers,
  registered apps, image cleanup policy, GitHub Environments and secrets, runners.
- `smoke` (default, includes the others) — live endpoints: `health` (and `demoEcho` if the demo is
  installed) per environment, last CI run on main.

`--ci` skips the workstation module; `--json` for machine-readable output. Exit 1 on any FAIL.
Needs `gcloud`/`gh` logged in for `cloud`/`smoke`. If Java isn't on PATH, check `~/.zshrc`.

## 2. Checks that need judgment or local runtimes (Claude)

Only for enabled modules, after the script passes:
- `firebase`: emulator smoke — `firebase emulators:exec -P dev --only functions,firestore,auth "<curl health>"`.
- `expo` / `expo-ios`: `npx expo config --type public` in the app shows the dev variant bundle id and EAS projectId.
- `e2e-maestro`: `maestro test` on the demo/smoke flow if a simulator is booted.
- Spot-check DEVINFRA.md decisions against reality (e.g. a decision says "no prod", spec has prod).

## 3. Report

Summarize per module: OK / WARN / FAIL counts; list each FAIL with its fix and each WARN worth
acting on. Offer to apply fixes, each through the owning module skill (verify itself never changes
anything). Add or update a line in DEVINFRA.md under "Open items": `Last verified <date>: <n> failures`.
