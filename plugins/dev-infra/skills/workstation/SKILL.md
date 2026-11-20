---
name: workstation
description: dev-infra core module. Checks and sets up the developer machine — Homebrew, git, GitHub CLI, Node/pnpm, Google Cloud CLI, Firebase CLI — and their logins. Use at the start of a project, on a new machine, or when a CLI is missing or logged out.
---

# Module: workstation

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.
Platform-specific toolchains (Xcode, JDK, EAS, Maestro) belong to their modules, not here.

**Requires:** —

## Steps

1. **Homebrew, git** — Check: `brew --version`, `git --version`.
   User: install Homebrew from https://brew.sh if missing.
2. **GitHub CLI** — Check: `gh auth status` (logged in; scopes include `repo`, `workflow`).
   Configure: `brew install gh`. User (separate terminal): `gh auth login`; missing scope: `gh auth refresh -s workflow`.
3. **Node + pnpm** — Check: `node -v`, `pnpm -v`. Odd/"current" Node majors are fine for tooling;
   the project pins an LTS (`project-repo`). Configure: `corepack enable pnpm`.
4. **Google Cloud CLI** — Check: `gcloud auth list` has an active account.
   Configure: `brew install --cask google-cloud-sdk`. User (separate terminal): `gcloud auth login`.
5. **Firebase CLI** — Check: `firebase --version`; `firebase login:list` shows an account.
   Configure: `npm i -g firebase-tools`. User (separate terminal): `firebase login`.
   Should be the same Google account as gcloud; if not, ask which one owns the projects.
6. **Java 21+** (Firebase emulators for Firestore/Auth; Maestro) — Check: `java -version` ≥ 21.
   Configure (no sudo): `brew install openjdk@21` and add `$(brew --prefix openjdk@21)/bin` to PATH in `~/.zshrc`.
   (`brew install --cask zulu@21` needs sudo → user runs it in a separate terminal.)

7. **Claude in Chrome** (optional; lets Claude drive web consoles in the user's own signed-in browser: Apple
   Developer portal for `monetization-adapty`, App Store Connect, checking web pages for `demo`/`web-nextjs`).
   Check: the `mcp__claude-in-chrome__*` tools are available in this session (or `/mcp` lists `claude-in-chrome`).
   Requirements: Chrome or another Chromium browser (not inside WSL), the extension
   https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn (v1.0.36+), Claude Code signed in
   with `/login` on a Pro/Max/Team/Enterprise plan (not API keys or Bedrock/Vertex), extension and Claude Code signed in
   to the **same account and organization**.
   User: install the extension and sign in; then in this session type `/chrome` → enable (and choose
   "Enabled by default" to skip this next time). No restart needed; new sessions can also start with `claude --chrome`.
   Troubleshooting: Chrome running and extension enabled in `chrome://extensions`; `/chrome` → Reconnect extension;
   `/status` to compare accounts/orgs; if still not detected, restart Chrome and Claude Code. Without it, browser steps
   fall back to exact click-by-click instructions for the user. Docs: https://code.claude.com/docs/en/chrome.md

## Done when

All checks pass; record the accounts (GitHub user, Google account) in DEVINFRA.md notes.
