#!/usr/bin/env python3
"""Check that the expected self-hosted runners are registered with GitHub, online and labeled.

Usage:
  check_runners.py --repo OWNER/REPO --expect NAME:label1,label2 [--expect ...]
  check_runners.py --org ORG --expect ...

Token: $GH_TOKEN or $GITHUB_TOKEN, else `gh auth token`. Listing runners needs
"Administration: read" on the repo (fine-grained PAT) or "Self-hosted runners: read" on the
org. The workflow GITHUB_TOKEN can't do this, so CI uses a dedicated PAT secret.

Exit code: 0 all good, 1 a runner is missing/offline/mislabeled, 2 API/auth error.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")


def token():
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sys.exit("error: no token (set GH_TOKEN or run `gh auth login`)")


def list_runners(base, tok):
    runners, page = [], 1
    while True:
        req = urllib.request.Request(
            f"{API}/{base}/actions/runners?per_page=100&page={page}",
            headers={
                "Authorization": f"Bearer {tok}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            hint = " (token lacks Administration: read?)" if e.code in (403, 404) else ""
            print(f"error: GitHub API {e.code} for {base}{hint}", file=sys.stderr)
            sys.exit(2)
        except urllib.error.URLError as e:
            print(f"error: cannot reach {API}: {e.reason}", file=sys.stderr)
            sys.exit(2)
        runners += data.get("runners", [])
        if len(runners) >= data.get("total_count", 0) or not data.get("runners"):
            return runners
        page += 1


def main():
    p = argparse.ArgumentParser()
    scope = p.add_mutually_exclusive_group(required=True)
    scope.add_argument("--repo")
    scope.add_argument("--org")
    p.add_argument("--expect", action="append", default=[], metavar="NAME:LABELS")
    args = p.parse_args()

    base = f"repos/{args.repo}" if args.repo else f"orgs/{args.org}"
    runners = {r["name"]: r for r in list_runners(base, token())}
    failed = False

    for spec in args.expect:
        name, _, labels = spec.partition(":")
        want = {l.strip().lower() for l in labels.split(",") if l.strip()}
        r = runners.pop(name, None)
        if r is None:
            print(f"FAIL  {name}: not registered with {base}")
            failed = True
            continue
        have = {l["name"].lower() for l in r.get("labels", [])}
        problems = []
        if r["status"] != "online":
            problems.append(f"status={r['status']}")
        if want - have:
            problems.append(f"missing labels {sorted(want - have)}")
        state = "busy" if r.get("busy") else "idle"
        if problems:
            failed = True
            print(f"FAIL  {name}: {', '.join(problems)} (labels: {sorted(have)})")
        else:
            print(f"OK    {name}: online, {state}, {r.get('os', '?')}, labels {sorted(have)}")

    for name, r in runners.items():
        print(f"WARN  {name}: registered but not expected (status={r['status']})")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
