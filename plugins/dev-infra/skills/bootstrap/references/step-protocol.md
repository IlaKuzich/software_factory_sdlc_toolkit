# Step protocol (all modules)

For every step:

1. **Check** — run the check. If it passes, say so in one line and go on.
2. **Configure** — if a command fixes it, show the command and why.
   - Without asking: read-only checks, local file edits inside the project.
   - Ask first: installs, creating cloud resources, anything that costs money or is hard to undo
     (project IDs, regions, billing links, repo visibility, store listings).
3. **User** — when a human is needed (sign-up, payment, browser consent, sudo, interactive login):
   give the exact URL/command, what to click/choose, the typical wait, and **what to send back**.
   **Where the user runs commands** — `! <command>` in the Claude Code prompt has no interactive stdin/TTY:
   - `! <command>` only for non-interactive commands whose output Claude should see.
   - **Separate terminal window** for anything that prompts: logins (`gh auth login`, `gcloud auth login`,
     `firebase login`, `eas login`), menus (`eas credentials`), secret entry (`gh secret set`, `eas env:create`
     with a hidden value), `sudo`. Give the exact command (with `cd <dir> &&`) and the answers to choose
     at each prompt; then the user reports back and Claude re-checks.
4. **Re-check** after the user reports done. Don't advance until it passes or the user
   explicitly defers it; record deferrals with the reason in DEVINFRA.md.
5. **Record** decisions (DEVINFRA.md) and non-secret values (`.dev-infra/environments.yaml`).
   Before `project-repo` creates these files, keep them in the conversation and write them then.

Rules:
- **Secrets never pass through the chat.** The user sets them in a separate terminal via `gh secret set NAME`,
  `eas env:create ... --visibility secret`, `firebase functions:secrets:set NAME` (each prompts for the value).
- Decisions: concrete options + a recommendation; flag irreversible ones.
- Paid items: state the price before asking the user to pay.
- Long waits (Apple/Google verification): start early, continue with other steps meanwhile.
- Keep the user oriented: `<module> · step n/N` and what it unlocks.
