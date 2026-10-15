#!/usr/bin/env bash
# Self-hosted runner doctor for macOS (iOS builds) and Linux/WSL2 (Android builds).
# Checks network reachability, runner registration/service, toolchain and host settings.
#
# Usage: runner_doctor.sh --platform ios|android [--runner-dir DIR]
# Inside a GitHub Actions job, registration/service checks are skipped (the job running proves them).
# Exit code: 0 no failures (warnings allowed), 1 at least one failure.
# Bash 3.2 compatible (macOS default shell).

set -u
PLATFORM=""
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner}"
while [ $# -gt 0 ]; do
  case "$1" in
    --platform) PLATFORM="$2"; shift 2 ;;
    --runner-dir) RUNNER_DIR="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
case "$PLATFORM" in ios|android) ;; *) echo "usage: $0 --platform ios|android [--runner-dir DIR]" >&2; exit 2 ;; esac

FAILS=0; WARNS=0
ok()   { printf 'OK    %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; WARNS=$((WARNS + 1)); }
fail() { printf 'FAIL  %s\n' "$*"; FAILS=$((FAILS + 1)); }
section() { printf '\n== %s ==\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

OS="$(uname -s)"
IS_WSL=0; [ -r /proc/version ] && grep -qi microsoft /proc/version && IS_WSL=1
IN_ACTIONS="${GITHUB_ACTIONS:-false}"

section "Host"
ok "$OS $(uname -m)$([ $IS_WSL = 1 ] && echo ' (WSL2)')"
if [ "$PLATFORM" = ios ] && [ "$OS" != Darwin ]; then fail "iOS builds require macOS"; fi
if [ "$PLATFORM" = android ] && [ "$OS" = Darwin ]; then warn "Android runner on macOS: fine, but spec expects Linux/WSL"; fi

free_gb=$(df -Pk "$HOME" | awk 'NR==2 {print int($4/1048576)}')
if [ "$free_gb" -lt 20 ]; then fail "free disk ${free_gb}GB < 20GB (builds + caches need room)"; else ok "free disk ${free_gb}GB"; fi

if [ "$OS" = Darwin ]; then
  sleep_min=$(pmset -g 2>/dev/null | awk '$1=="sleep" {print $2}')
  if [ "${sleep_min:-1}" != 0 ]; then warn "system sleep is ${sleep_min:-?} min; set 'sudo pmset -a sleep 0' so the runner stays reachable"; else ok "system sleep disabled"; fi
  auto_login=$(defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser 2>/dev/null || true)
  if [ -z "$auto_login" ]; then warn "no automatic login: the runner LaunchAgent (svc.sh) only runs in a logged-in session, so it won't come back after a reboot"; else ok "automatic login as $auto_login"; fi
fi
if [ $IS_WSL = 1 ]; then
  warn "WSL2: the runner stops when the laptop sleeps or WSL shuts down; check Windows power settings with runner_doctor.ps1 -HostOnly"
fi

section "Network"
check_host() {
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "https://$1" 2>/dev/null || true)
  if [ -z "$code" ] || [ "$code" = 000 ]; then fail "cannot reach https://$1"; else ok "https://$1 (HTTP $code)"; fi
}
if ! have curl; then fail "curl not installed"; else
  for h in github.com api.github.com codeload.github.com \
           pipelines.actions.githubusercontent.com results-receiver.actions.githubusercontent.com \
           broker.actions.githubusercontent.com objects.githubusercontent.com pkg.actions.githubusercontent.com \
           registry.npmjs.org api.expo.dev firebase.googleapis.com; do
    check_host "$h"
  done
  if [ "$PLATFORM" = ios ]; then check_host cdn.cocoapods.org; fi
  if [ "$PLATFORM" = android ]; then check_host dl.google.com; check_host services.gradle.org; check_host repo.maven.apache.org; fi
fi

section "Runner"
if [ "$IN_ACTIONS" = true ]; then
  ok "running inside a GitHub Actions job on runner '${RUNNER_NAME:-?}' (registration and service proven)"
else
  if [ ! -f "$RUNNER_DIR/.runner" ]; then
    fail "no runner configured in $RUNNER_DIR (pass --runner-dir, or run config.sh)"
  else
    info=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8-sig")); print(d.get("agentName","?"), d.get("gitHubUrl","?"))' "$RUNNER_DIR/.runner" 2>/dev/null || echo "? ?")
    ok "configured: name=${info%% *} url=${info#* }"
    if pgrep -f Runner.Listener >/dev/null 2>&1; then ok "Runner.Listener process is running"; else fail "Runner.Listener not running (start: cd $RUNNER_DIR && ./svc.sh start)"; fi
    if [ -x "$RUNNER_DIR/bin/Runner.Listener" ]; then
      ver=$("$RUNNER_DIR/bin/Runner.Listener" --version 2>/dev/null | tr -d '[:space:]')
      latest=$(curl -sS --max-time 10 https://api.github.com/repos/actions/runner/releases/latest 2>/dev/null | sed -n 's/.*"tag_name": *"v\([^"]*\)".*/\1/p')
      if [ -n "$latest" ] && [ -n "$ver" ] && [ "$ver" != "$latest" ]; then
        warn "runner $ver, latest $latest (runners self-update; very old versions get rejected by GitHub)"
      else ok "runner version ${ver:-?}"; fi
    fi
  fi
fi

section "Toolchain"
need() {  # need <cmd> <hint>
  if have "$1"; then ok "$1: $("$1" --version 2>&1 | head -1)"; else fail "$1 not found ($2)"; fi
}
need git "install git"
if have node; then
  major=$(node -p 'process.versions.node.split(".")[0]')
  if [ "$major" -lt 20 ]; then fail "node $(node -v) < 20"; else ok "node $(node -v)"; fi
else fail "node not found (install Node 20+ or let actions/setup-node provide it)"; fi
if have pnpm; then ok "pnpm $(pnpm -v)"; else warn "pnpm not on PATH (fine if workflows use pnpm/action-setup or corepack)"; fi
if have eas; then ok "eas-cli $(eas --version 2>/dev/null | head -1)"; else warn "eas-cli not global (workflows use npx eas-cli)"; fi

if [ "$PLATFORM" = ios ]; then
  dev_dir=$(xcode-select -p 2>/dev/null || true)
  case "$dev_dir" in
    ""|*CommandLineTools*)
      if [ -d /Applications/Xcode.app ]; then fail "Xcode installed but not selected; run 'sudo xcode-select -s /Applications/Xcode.app'"
      else fail "full Xcode not installed (only Command Line Tools); install Xcode from the App Store"; fi ;;
    *)
      ok "$(xcodebuild -version 2>/dev/null | tr '\n' ' ')at $dev_dir"
      if xcodebuild -checkFirstLaunchStatus >/dev/null 2>&1; then ok "Xcode first-launch/license done"; else fail "run 'sudo xcodebuild -runFirstLaunch' and accept the license"; fi ;;
  esac
  need pod "gem install cocoapods (or brew install cocoapods)"
  if have fastlane; then ok "fastlane $(fastlane --version 2>/dev/null | grep -Eo 'fastlane [0-9.]+' | head -1 | cut -d' ' -f2)"
  else fail "fastlane not found (brew install fastlane; required by eas build --local)"; fi
fi

if [ "$PLATFORM" = android ]; then
  if have java; then
    jv=$(java -version 2>&1 | head -1 | sed -n 's/.*version "\([0-9]*\).*/\1/p')
    if [ "${jv:-0}" != 17 ]; then warn "Java ${jv:-?}; React Native/Expo builds expect JDK 17"; else ok "Java 17"; fi
  else fail "java not found (install JDK 17)"; fi
  sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  if [ -z "$sdk" ] || [ ! -d "$sdk" ]; then fail "ANDROID_HOME not set or missing; must be set in the runner's .env file too"
  else
    ok "Android SDK at $sdk"
    [ -d "$sdk/platform-tools" ] && ok "platform-tools present" || fail "platform-tools missing (sdkmanager 'platform-tools')"
    [ -d "$sdk/build-tools" ] && ok "build-tools: $(ls "$sdk/build-tools" | tr '\n' ' ')" || fail "build-tools missing"
    if [ "$IN_ACTIONS" != true ] && [ -f "$RUNNER_DIR/.env" ] && ! grep -q '^ANDROID_HOME=' "$RUNNER_DIR/.env"; then
      warn "ANDROID_HOME not in $RUNNER_DIR/.env; jobs may not see it"
    fi
  fi
  if [ $IS_WSL = 1 ]; then
    mem_gb=$(awk '/MemTotal/ {print int($2/1048576)}' /proc/meminfo)
    if [ "$mem_gb" -lt 8 ]; then warn "WSL has ${mem_gb}GB RAM; Gradle builds want 8GB+ (set memory= in %UserProfile%\\.wslconfig)"; else ok "WSL memory ${mem_gb}GB"; fi
  fi
fi

printf '\n%d failure(s), %d warning(s)\n' "$FAILS" "$WARNS"
[ "$FAILS" -eq 0 ]
