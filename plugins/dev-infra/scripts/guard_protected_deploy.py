"""PreToolUse hook: ask for confirmation before deploying to a protected environment.

Protected environments come from `protected_environments` in
.dev-infra/environments.yaml. A deploy command (firebase deploy, eas build/update/submit,
firebase apphosting rollouts, gh workflow run) is flagged if it mentions a protected environment's name or
any of its values (Firebase project id, EAS profile/channel/environment).

Stdlib only, with a minimal line-based reader for the spec's simple YAML shape.
"""

import json
import os
import re
import sys

SPEC = os.path.join(".dev-infra", "environments.yaml")
DEFAULT_TOKENS = {"prod", "production"}
DEPLOY_RE = re.compile(
    r"\bfirebase\b[^;&|]*\b(deploy|apphosting:rollouts:create|hosting:channel:deploy)\b"
    r"|\beas\b[^;&|]*\b(build|update|submit|deploy)\b"
    r"|\bgh\b[^;&|]*\bworkflow\s+run\b"
)


def protected_tokens(spec_path):
    try:
        with open(spec_path) as f:
            lines = f.read().splitlines()
    except OSError:
        return DEFAULT_TOKENS

    protected = []
    for line in lines:
        m = re.match(r"^protected_environments:\s*\[(.*)\]", line)
        if m:
            protected = [p.strip().strip("'\"") for p in m.group(1).split(",") if p.strip()]
    if not protected:
        return DEFAULT_TOKENS

    tokens = set(protected)
    in_envs, current = False, None
    for line in lines:
        stripped = line.split("#", 1)[0].rstrip()
        if not stripped:
            continue
        indent = len(stripped) - len(stripped.lstrip())
        if indent == 0:
            in_envs = stripped.startswith("environments:")
            current = None
        elif in_envs and indent == 2 and stripped.endswith(":"):
            current = stripped.strip()[:-1]
        elif in_envs and current in protected and ":" in stripped:
            value = stripped.split(":", 1)[1].strip().strip("'\"")
            if value:
                tokens.add(value)
    return tokens


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    command = payload.get("tool_input", {}).get("command", "")
    if not DEPLOY_RE.search(command):
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."
    tokens = protected_tokens(os.path.join(project_dir, SPEC))
    words = set(re.split(r"[\s=,'\"]+", command))
    hits = sorted(tokens & words)
    if not hits:
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": (
                f"dev-infra: this deploys to a protected environment ({', '.join(hits)}). Confirm to proceed."
            ),
        }
    }))


if __name__ == "__main__":
    main()
