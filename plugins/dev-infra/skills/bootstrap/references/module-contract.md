# Module contract

Every dev-infra module is a skill `skills/<id>/SKILL.md` registered in `modules.yaml`.
Modules are independent: each can be run on its own (`/dev-infra:<id>`) to add, resume or
re-verify that part of the infra, e.g. adding Android to a project that started iOS-only.

## SKILL.md sections (in this order)

1. **Frontmatter** — `name: <id>`; `description` says what it sets up and when to use it.
2. **Requires** — module ids; if one isn't `done` in DEVINFRA.md, run it first (or ask).
3. **Decisions** — questions to ask the user, each with options + a recommendation.
   Record every answer in DEVINFRA.md (see below); values also go to `.dev-infra/environments.yaml`.
4. **Steps** — ordered, idempotent, each with **Check / Configure / User / Record**,
   executed with [step-protocol.md](step-protocol.md).
5. **Done when** — the checks that prove the module works end to end.

## Effects on the project

- On start: set the module's row in DEVINFRA.md to `in progress`.
- On finish: `done` (or `deferred: <reason>` for skipped steps); update the
  CLAUDE.md managed block's module list (see [devinfra-template.md](devinfra-template.md)).
- A module may add a section to `.dev-infra/environments.yaml`; only its own keys.
- Disabling a module: set `not used` in DEVINFRA.md with the reason; don't delete files
  without asking.
