---
name: e2e-playwright
description: dev-infra service module. Playwright end-to-end tests for the Next.js web app — install, config that runs the same tests locally (starting Next) or against a deployed environment URL, Turborepo task, and hooks for CI (PR checks and post-deploy smoke). Use when adding web E2E tests or when they fail on setup issues.
---

# Module: e2e-playwright

Steps run with `${CLAUDE_PLUGIN_ROOT}/skills/bootstrap/references/step-protocol.md`.

**Requires:** web-nextjs

## Decisions

- **Browsers** — Chromium only (recommended to start; fastest in CI) or also WebKit/Firefox.
- **What PR runs hit** — the dev Firebase project (simplest) or emulators (`NEXT_PUBLIC_USE_EMULATORS=1`,
  isolated, needs Java in CI).

## Steps

1. **Install** — Check: `@playwright/test` in `apps/web/package.json`, `npx playwright --version`.
   Configure: `pnpm --filter web add -D @playwright/test`; `npx playwright install chromium`
   (CI: `npx playwright install --with-deps chromium`).
2. **Config** — `apps/web/playwright.config.ts`:
   - `baseURL = process.env.E2E_BASE_URL ?? "http://localhost:<port>"`; when `E2E_BASE_URL` is unset, a
     `webServer` starts Next (`pnpm dev --port <port>` locally, `pnpm start --port <port>` in CI after the build),
     `reuseExistingServer: !CI`. Pick a free port (`lsof -nP -iTCP:<port> -sTCP:LISTEN`).
   - `retries: CI ? 1 : 0`, `trace: "retain-on-failure"`, reporter `github` + `html` in CI.
   - Tests in `apps/web/e2e/`; selectors by `data-testid` (`page.getByTestId`).
   - Environment-aware assertions read `E2E_EXPECT_ENV` (default `dev`), so a post-deploy smoke catches a
     build that shipped another environment's config.
3. **Scripts + Turborepo** — app script `"e2e": "playwright test"`; `turbo.json` task
   `"e2e": {"cache": false, "env": ["E2E_BASE_URL", "E2E_EXPECT_ENV", "CI"]}` (live targets must not be cached;
   Turbo strips undeclared env vars). `.gitignore`: `/test-results/`, `/playwright-report/`, `/playwright/.cache/`.
4. **Run** — locally: `pnpm --filter web e2e`; against an environment:
   `E2E_BASE_URL=<backend url> E2E_EXPECT_ENV=<env> pnpm turbo run e2e --filter web`.
   Negative check once: a wrong `E2E_EXPECT_ENV` must fail.
5. **CI** (with `ci-cd`) — the CI build uses `apps/web/.env` (default dev config; see `web-nextjs`). PR job on `ubuntu-latest`: install browsers, `turbo run build --filter web`, `CI=1 pnpm --filter web e2e`;
   post-deploy job in `deploy.yml`: `E2E_BASE_URL` = the environment's App Hosting URL, `E2E_EXPECT_ENV` = env name;
   upload `playwright-report` on failure.

## Done when

The suite passes locally and against the dev backend URL; the negative env check fails as expected.
