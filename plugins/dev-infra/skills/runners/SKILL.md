---
name: runners
description: dev-infra service module. Set up and check the GitHub Actions self-hosted runners (Mac mini for iOS, Windows laptop/WSL2 for Android) — registration and online status via the GitHub API, network connectivity to GitHub/Expo/Firebase, runner service, toolchain (Xcode, CocoaPods, fastlane, JDK, Android SDK, Node) and host settings (sleep, auto-login, lid close). Use when the user asks whether runners are up, why a job is stuck queued, or to verify a runner machine's configuration.
---

# Module: runners

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.

**Requires:** ci-cd

## Decisions

- **Machines** — Mac mini for iOS (if `expo-ios`), Windows laptop for Android (if `expo-android`).
- **Windows mode** — WSL2 (recommended; `eas build --local` needs Linux/macOS) or native Windows.
- **Scope** — repo-level runners (personal account) or org-level (shared across repos).
- **Remote access** — SSH address per machine (optional), so checks can run from here.

## Setup (per machine, mostly done by the user on that machine)

Follow `${CLAUDE_PLUGIN_ROOT}/skills/ci-cd/references/runners.md`. Claude provides the
registration token (`gh api -X POST repos/<repo>/actions/runners/registration-token --jq .token`,
valid 1h) and the exact commands; the user runs them on the machine and reports back.
Record each machine in `ci.runners` (environments.yaml) and in DEVINFRA.md.

# Health check

Expected runners come from `ci.runners` in `.dev-infra/environments.yaml`.
Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`. Run the layers in order and stop
to explain at the first layer that fails: later layers depend on it.

## 1. Registered and online (GitHub API)

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_runners.py" --repo <ci.github_repo> \
  --expect "<name>:<label1>,<label2>,..."   # one --expect per ci.runners entry
```

Uses the local `gh` login. A 403/404 means the token can't administer the repo.
- `not registered` → registration steps in the `ci-cd` skill's `references/runners.md`.
- `status=offline` → the machine is asleep or off, or the service stopped: go to layer 2.
- `missing labels` → workflows targeting those labels will queue forever; re-run `config.sh`
  with `--labels`, or fix `runs-on` in the workflows.

## 2. On the machine

Pick by where you are:
- **This machine is the runner** (compare `hostname` / `uname`): run
  `bash "${CLAUDE_PLUGIN_ROOT}/scripts/runner_doctor.sh" --platform <ios|android>`.
- **The runner has `ssh:` in the spec**: stream the script over SSH (nothing to install there):
  `ssh <ssh> 'bash -s -- --platform <platform>' < "${CLAUDE_PLUGIN_ROOT}/scripts/runner_doctor.sh"`.
  For `os: windows`, use `ssh <ssh> powershell -NoProfile -Command -` with `runner_doctor.ps1` piped in.
  For `os: wsl`, also check the Windows host: `runner_doctor.ps1 -HostOnly` (on Windows).
- **Otherwise**: give the user the exact command to run on that machine, or point them to
  layer 3, which runs the same doctor through GitHub.

## 3. End to end (through GitHub Actions)

If the project has `.github/workflows/runner-health.yml`:

```sh
gh workflow run runner-health.yml && sleep 5 && gh run watch "$(gh run list -w runner-health.yml -L1 --json databaseId -q '.[0].databaseId')"
```

This proves the whole path: GitHub dispatches a job → the runner picks it up → it checks out
code and reaches the network. If it stays queued, layer 1 is failing.

## Done when

All three layers pass for every runner in `ci.runners`.

## Reporting

Summarize per runner: registered/online, labels, failures with the fix for each, warnings
worth acting on (sleep, auto-login, disk). Don't change machine settings yourself; give commands.
