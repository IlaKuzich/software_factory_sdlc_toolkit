#!/usr/bin/env python3
"""Read-only verification of a dev-infra project.

Checks the modules that DEVINFRA.md marks as `done` or `in progress`, on three levels:
  config  files in the repo agree with .dev-infra/environments.yaml
  cloud   GitHub / Google Cloud / Firebase state matches the spec (read-only API calls)
  smoke   live endpoints respond (health function per environment, last CI run)
Levels are cumulative: --level cloud runs config + cloud.

Usage: verify_project.py [--project DIR] [--level config|cloud|smoke] [--ci] [--json]
  --ci   skip workstation checks (tools/logins of a developer machine)
Exit code: 0 no failures, 1 failures, 2 cannot run (no spec / no YAML parser).
Needs: python3; PyYAML or ruby (to read YAML); gh, gcloud for cloud level.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

LEVELS = ["config", "cloud", "smoke"]
ACTIVE = ("done", "in progress")


class Report:
    def __init__(self):
        self.rows = []

    def add(self, module, level, check, status, detail="", fix=""):
        self.rows.append(dict(module=module, level=level, check=check, status=status, detail=detail, fix=fix))

    def ok(self, m, l, c, d="", fix=""):  # fix accepted so ok/fail are interchangeable
        self.add(m, l, c, "OK", d)

    def warn(self, m, l, c, d="", fix=""):
        self.add(m, l, c, "WARN", d, fix)

    def fail(self, m, l, c, d="", fix=""):
        self.add(m, l, c, "FAIL", d, fix)

    def skip(self, m, l, c, d=""):
        self.add(m, l, c, "SKIP", d)


# ---------- helpers ----------

def load_yaml(path):
    try:
        import yaml  # type: ignore
        with open(path) as f:
            return yaml.safe_load(f)
    except ImportError:
        pass
    if shutil.which("ruby"):
        out = subprocess.run(["ruby", "-ryaml", "-rjson", "-e", "puts JSON.dump(YAML.load_file(ARGV[0]))", path],
                             capture_output=True, text=True)
        if out.returncode == 0:
            return json.loads(out.stdout)
    sys.exit("error: need PyYAML (pip install pyyaml) or ruby to read YAML")


def sh(*cmd, timeout=60):
    """Run a command; return (exit_code, stdout). Missing binary -> (127, '')."""
    if not shutil.which(cmd[0]):
        return 127, ""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip()
    except subprocess.TimeoutExpired:
        return 124, ""


_token = None


def gtoken():
    global _token
    if _token is None:
        code, out = sh("gcloud", "auth", "print-access-token")
        _token = out if code == 0 else ""
    return _token


def http_json(url, project=None, timeout=20):
    """GET with Google auth; return (status, json|None)."""
    headers = {"Authorization": f"Bearer {gtoken()}"}
    if project:
        headers["x-goog-user-project"] = project
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, None
    except (urllib.error.URLError, TimeoutError):
        return 0, None


def http_get(url, timeout=20):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, str(e)


def http_post_json(url, payload, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, None
    except (urllib.error.URLError, TimeoutError):
        return 0, None


def module_statuses(devinfra_path):
    statuses = {}
    with open(devinfra_path) as f:
        for line in f:
            m = re.match(r"^\|\s*([a-z][a-z0-9-]*)\s*\|\s*([^|]+?)\s*\|", line)
            if m and m.group(1) != "module":
                statuses[m.group(1)] = m.group(2).lower()
    return statuses


def variant_suffix(env_name, env):
    return "" if env.get("app_variant") == "production" else f".{env_name}"


# ---------- module checks ----------

def check_workstation(r, spec, enabled, level):
    M = "workstation"
    for tool in ["git", "gh", "node", "pnpm", "gcloud", "firebase"]:
        (r.ok if shutil.which(tool) else r.fail)(M, "config", f"{tool} installed", "" if shutil.which(tool) else "not on PATH")
    if "firebase" in enabled or "e2e-maestro" in enabled:
        # `java -version` prints to stderr
        err = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr if shutil.which("java") else ""
        m = re.search(r'version "(\d+)', err)
        if m and int(m.group(1)) >= 21:
            r.ok(M, "config", "java >= 21", f"java {m.group(1)}")
        else:
            r.fail(M, "config", "java >= 21", "missing or too old", "brew install openjdk@21")
    if LEVELS.index(level) >= 1:
        code, _ = sh("gh", "auth", "status")
        (r.ok if code == 0 else r.fail)(M, "cloud", "gh logged in", "", "gh auth login")
        code, out = sh("gcloud", "config", "get-value", "account")
        (r.ok if out else r.fail)(M, "cloud", "gcloud account", out, "gcloud auth login")
        code, out = sh("firebase", "login:list")
        logged = "@" in out
        (r.ok if logged else r.fail)(M, "cloud", "firebase logged in", "", "firebase login")


def check_project_repo(r, spec, root, level):
    M = "project-repo"
    for f in ["pnpm-workspace.yaml", "package.json", ".nvmrc", ".dev-infra/DEVINFRA.md", ".dev-infra/environments.yaml"]:
        p = os.path.join(root, f)
        (r.ok if os.path.exists(p) else r.fail)(M, "config", f"{f} exists")
    claude = os.path.join(root, "CLAUDE.md")
    has_block = os.path.exists(claude) and "<!-- dev-infra:begin" in open(claude).read()
    (r.ok if has_block else r.fail)(M, "config", "CLAUDE.md dev-infra block", "", "re-run /dev-infra:project-repo step 3")
    if LEVELS.index(level) >= 1:
        repo = spec.get("ci", {}).get("github_repo", "")
        code, out = sh("gh", "repo", "view", repo, "--json", "nameWithOwner,visibility")
        if code != 0:
            r.fail(M, "cloud", "GitHub repo exists", repo, "check ci.github_repo")
        else:
            info = json.loads(out)
            r.ok(M, "cloud", "GitHub repo exists", info["nameWithOwner"])
            if info["visibility"] != "PRIVATE":
                r.warn(M, "cloud", "repo is private", info["visibility"], "self-hosted runners + public repo = fork PRs run on your machines")
            else:
                r.ok(M, "cloud", "repo is private")


def check_firebase(r, spec, root, enabled, level):
    M = "firebase"
    envs = spec.get("environments", {})
    fb = spec.get("firebase", {})
    region = fb.get("functions_region", "us-central1")
    # config
    rc_path = os.path.join(root, ".firebaserc")
    aliases = json.load(open(rc_path)).get("projects", {}) if os.path.exists(rc_path) else {}
    for name, env in envs.items():
        pid = env.get("firebase_project")
        if aliases.get(name) == pid:
            r.ok(M, "config", f".firebaserc alias {name}", pid)
        else:
            r.fail(M, "config", f".firebaserc alias {name}", f"is {aliases.get(name)!r}, spec {pid!r}", "run /dev-infra:environments")
        envfile = os.path.join(root, spec.get("apps", {}).get("functions", {}).get("path", "functions"), f".env.{name}")
        (r.ok if os.path.exists(envfile) else r.warn)(M, "config", f"functions/.env.{name}")
    protected = set(spec.get("protected_environments", []))
    default = aliases.get("default")
    if default and any(envs.get(p, {}).get("firebase_project") == default for p in protected):
        r.fail(M, "config", ".firebaserc default not protected", default, "point default at dev")
    fj = os.path.join(root, "firebase.json")
    if os.path.exists(fj):
        conf = json.load(open(fj))
        funcs = conf.get("functions")
        funcs = funcs if isinstance(funcs, list) else [funcs] if funcs else []
        want = spec.get("apps", {}).get("functions", {}).get("runtime")
        got = funcs[0].get("runtime") if funcs else None
        (r.ok if not want or got == want else r.fail)(M, "config", "functions runtime", f"{got}", f"set runtime {want} in firebase.json")
    else:
        r.fail(M, "config", "firebase.json exists")

    if LEVELS.index(level) < 1:
        return
    if not gtoken():
        r.fail(M, "cloud", "gcloud access token", "", "gcloud auth login")
        return
    want_apis = ["firestore.googleapis.com", "cloudfunctions.googleapis.com", "cloudbuild.googleapis.com",
                 "artifactregistry.googleapis.com", "run.googleapis.com", "secretmanager.googleapis.com",
                 "identitytoolkit.googleapis.com"]
    if "web-nextjs" in enabled:
        want_apis.append("firebaseapphosting.googleapis.com")
    providers = fb.get("auth_providers", [])
    bundle = spec.get("apps", {}).get("mobile", {}).get("bundle_id", "")

    for name, env in envs.items():
        pid = env["firebase_project"]
        tag = f"[{name}]"
        code, out = sh("gcloud", "billing", "projects", "describe", pid, "--format=value(billingEnabled)")
        if code != 0:
            r.fail(M, "cloud", f"{tag} project + billing", "project not found or no access")
            continue
        (r.ok if out == "True" else r.fail)(M, "cloud", f"{tag} Blaze billing", out, "gcloud billing projects link")
        code, out = sh("gcloud", "services", "list", "--enabled", "--project", pid, "--format=value(config.name)")
        enabled_apis = set(out.split())
        missing = [a for a in want_apis if a not in enabled_apis]
        (r.ok if not missing else r.fail)(M, "cloud", f"{tag} APIs enabled", ", ".join(missing), "gcloud services enable ...")
        st, db = http_json(f"https://firestore.googleapis.com/v1/projects/{pid}/databases/(default)", pid)
        loc = (db or {}).get("locationId")
        want_loc = fb.get("firestore_location")
        if st != 200:
            r.fail(M, "cloud", f"{tag} Firestore", f"HTTP {st}", "gcloud firestore databases create")
        elif want_loc and loc != want_loc:
            r.fail(M, "cloud", f"{tag} Firestore location", f"{loc} (spec {want_loc}; location can't change)")
        else:
            r.ok(M, "cloud", f"{tag} Firestore", loc)
        # auth
        st, cfg = http_json(f"https://identitytoolkit.googleapis.com/admin/v2/projects/{pid}/config", pid)
        if st != 200:
            r.fail(M, "cloud", f"{tag} Auth initialized", (cfg or {}).get("error", {}).get("message", f"HTTP {st}"),
                   f"console: Authentication -> Get started")
        else:
            st2, idps = http_json(f"https://identitytoolkit.googleapis.com/admin/v2/projects/{pid}/defaultSupportedIdpConfigs", pid)
            on = {i["name"].rsplit("/", 1)[-1] for i in (idps or {}).get("defaultSupportedIdpConfigs", []) if i.get("enabled")}
            sign_in = cfg.get("signIn", {})
            if sign_in.get("anonymous", {}).get("enabled"):
                on.add("anonymous")
            if sign_in.get("email", {}).get("enabled"):
                on.add("password")
            missing = [p for p in providers if p not in on]
            (r.ok if not missing else r.fail)(M, "cloud", f"{tag} Auth providers", ", ".join(sorted(on)) if not missing else f"missing {missing}")
        # apps
        suffix = variant_suffix(name, env)
        if "expo-ios" in enabled:
            st, apps = http_json(f"https://firebase.googleapis.com/v1beta1/projects/{pid}/iosApps", pid)
            ids = {a.get("bundleId") for a in (apps or {}).get("apps", [])}
            want = bundle + suffix
            (r.ok if want in ids else r.fail)(M, "cloud", f"{tag} iOS app {want}", "", "firebase apps:create IOS")
        if "expo-android" in enabled:
            st, apps = http_json(f"https://firebase.googleapis.com/v1beta1/projects/{pid}/androidApps", pid)
            ids = {a.get("packageName") for a in (apps or {}).get("apps", [])}
            want = bundle + suffix
            (r.ok if want in ids else r.fail)(M, "cloud", f"{tag} Android app {want}", "", "firebase apps:create ANDROID")
        if "web-nextjs" in enabled or "expo" in enabled:
            st, apps = http_json(f"https://firebase.googleapis.com/v1beta1/projects/{pid}/webApps", pid)
            n = len((apps or {}).get("apps", []))
            (r.ok if n else r.fail)(M, "cloud", f"{tag} Web app registered", f"{n}", "firebase apps:create WEB")
        # artifact cleanup policy (repo appears after first functions deploy)
        st, repo = http_json(f"https://artifactregistry.googleapis.com/v1/projects/{pid}/locations/{region}/repositories/gcf-artifacts", pid)
        if st == 404:
            r.skip(M, "cloud", f"{tag} image cleanup policy", "no functions deployed yet")
        elif st == 200 and (repo or {}).get("cleanupPolicies"):
            r.ok(M, "cloud", f"{tag} image cleanup policy")
        else:
            r.warn(M, "cloud", f"{tag} image cleanup policy", "missing",
                   f"firebase functions:artifacts:setpolicy --location {region} -P {name} --force")

        if LEVELS.index(level) >= 2:
            url = f"https://{region}-{pid}.cloudfunctions.net/health"
            st, body = http_get(url)
            if st == 200 and '"ok":true' in body.replace(" ", ""):
                r.ok(M, "smoke", f"{tag} health endpoint", body.strip()[:80])
            elif st == 404:
                r.skip(M, "smoke", f"{tag} health endpoint", "not deployed")
            else:
                r.fail(M, "smoke", f"{tag} health endpoint", f"HTTP {st}")
            demo_src = os.path.join(root, spec.get("apps", {}).get("functions", {}).get("path", "functions"), "src", "demo.ts")
            if os.path.exists(demo_src):
                st, body = http_post_json(f"https://{region}-{pid}.cloudfunctions.net/demoEcho", {"data": {}})
                res = (body or {}).get("result", {}) if isinstance(body, dict) else {}
                if st == 200 and res.get("message", "").startswith("Hello from") and res.get("env") == name:
                    r.ok(M, "smoke", f"{tag} demoEcho callable", f"{res.get('message')} / env={res.get('env')}")
                elif st == 404:
                    r.skip(M, "smoke", f"{tag} demoEcho callable", "not deployed")
                else:
                    r.fail(M, "smoke", f"{tag} demoEcho callable", f"HTTP {st} {str(body)[:80]}", "see /dev-infra:demo")


def check_ci(r, spec, root, enabled, level):
    M = "ci-cd"
    wf = os.path.join(root, ".github", "workflows")
    want = ["ci.yml"] + (["deploy.yml"] if "firebase" in enabled else [])
    for f in want:
        (r.ok if os.path.exists(os.path.join(wf, f)) else r.fail)(M, "config", f"workflow {f}", "", "run /dev-infra:ci-cd")
    if LEVELS.index(level) < 1:
        return
    repo = spec.get("ci", {}).get("github_repo", "")
    code, out = sh("gh", "api", f"repos/{repo}/environments", "--jq", "[.environments[].name]")
    have = set(json.loads(out)) if code == 0 and out else set()
    for name in spec.get("environments", {}):
        (r.ok if name in have else r.fail)(M, "cloud", f"GitHub Environment {name}", "", f"gh api -X PUT repos/{repo}/environments/{name}")
        if name in have and "firebase" in enabled:
            code, out = sh("gh", "variable", "list", "--repo", repo, "--env", name, "--json", "name", "--jq", "[.[].name]")
            have_vars = set(json.loads(out)) if code == 0 and out else set()
            need = {"GCP_WIF_PROVIDER", "GCP_DEPLOY_SA", "FUNCTIONS_URL"} | ({"WEB_URL"} if "web-nextjs" in enabled else set())
            missing = sorted(need - have_vars)
            (r.ok if not missing else r.fail)(M, "cloud", f"[{name}] environment variables", ", ".join(missing) if missing else "", "see /dev-infra:ci-cd step 4")
    code, out = sh("gh", "secret", "list", "--repo", repo, "--json", "name", "--jq", "[.[].name]")
    secrets = set(json.loads(out)) if code == 0 and out else set()
    # Require only the secrets that workflows actually reference.
    wf_text = "".join(open(os.path.join(wf, f)).read() for f in os.listdir(wf) if f.endswith((".yml", ".yaml"))) if os.path.isdir(wf) else ""
    for name in re.findall(r"secrets\.([A-Z0-9_]+)", wf_text):
        if name == "GITHUB_TOKEN":
            continue
        (r.ok if name in secrets else r.fail)(M, "cloud", f"secret {name}", "used by workflows", f"gh secret set {name} --repo {repo}")
    if LEVELS.index(level) >= 2:
        code, out = sh("gh", "run", "list", "--repo", repo, "--workflow", "ci.yml", "--branch", "main", "-L", "1",
                       "--json", "conclusion,status,url")
        runs = json.loads(out) if code == 0 and out else []
        if not runs:
            r.skip(M, "smoke", "last CI run on main", "no runs yet")
        else:
            c = runs[0].get("conclusion") or runs[0].get("status")
            (r.ok if c == "success" else r.fail)(M, "smoke", "last CI run on main", f"{c} {runs[0]['url']}")


def check_expo(r, spec, root, enabled, level):
    mob = spec.get("apps", {}).get("mobile", {})
    path = os.path.join(root, mob.get("path", "apps/mobile"))
    if "expo" in enabled:
        (r.ok if os.path.exists(os.path.join(path, "package.json")) else r.fail)("expo", "config", "mobile app exists", path)
        (r.ok if mob.get("expo_owner") else r.warn)("expo", "config", "expo_owner in spec")
        if LEVELS.index(level) >= 1 and shutil.which("eas"):
            code, out = sh("eas", "whoami")
            (r.ok if code == 0 else r.fail)("expo", "cloud", "eas logged in", out.splitlines()[-1] if out else "", "eas login")
    if "expo-ios" in enabled:
        (r.ok if mob.get("apple_team_id") else r.warn)("expo-ios", "config", "apple_team_id in spec", mob.get("apple_team_id", ""))


def check_web(r, spec, root, enabled, level):
    web = spec.get("apps", {}).get("web", {})
    path = os.path.join(root, web.get("path", "apps/web"))
    (r.ok if os.path.exists(os.path.join(path, "package.json")) else r.fail)("web-nextjs", "config", "web app exists", path)


def check_maestro(r, root, spec):
    path = os.path.join(root, spec.get("apps", {}).get("mobile", {}).get("path", "apps/mobile"), ".maestro")
    (r.ok if shutil.which("maestro") else r.fail)("e2e-maestro", "config", "maestro installed", "", "curl -Ls https://get.maestro.mobile.dev | bash")
    (r.ok if os.path.isdir(path) else r.fail)("e2e-maestro", "config", "flows directory", path)


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.environ.get("CLAUDE_PROJECT_DIR", "."))
    ap.add_argument("--level", choices=LEVELS, default="smoke")
    ap.add_argument("--ci", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    root = os.path.abspath(a.project)
    spec_path = os.path.join(root, ".dev-infra", "environments.yaml")
    devinfra = os.path.join(root, ".dev-infra", "DEVINFRA.md")
    if not (os.path.exists(spec_path) and os.path.exists(devinfra)):
        print(f"error: {root} has no .dev-infra/environments.yaml + DEVINFRA.md (run /dev-infra:bootstrap)", file=sys.stderr)
        sys.exit(2)
    spec = load_yaml(spec_path) or {}
    statuses = module_statuses(devinfra)
    enabled = {m for m, s in statuses.items() if s != "not used"}
    active = {m for m, s in statuses.items() if s in ACTIVE}

    r = Report()

    if "workstation" in active and not a.ci:
        check_workstation(r, spec, enabled, a.level)
    if "project-repo" in active:
        check_project_repo(r, spec, root, a.level)
    if "firebase" in active:
        check_firebase(r, spec, root, enabled, a.level)
    if active & {"expo", "expo-ios", "expo-android"}:
        check_expo(r, spec, root, active, a.level)
    if "web-nextjs" in active:
        check_web(r, spec, root, active, a.level)
    if "ci-cd" in active:
        check_ci(r, spec, root, enabled, a.level)
    if "e2e-maestro" in active:
        check_maestro(r, root, spec)
    if "e2e-playwright" in active:
        web = os.path.join(root, spec.get("apps", {}).get("web", {}).get("path", "apps/web"))
        cfg = os.path.join(web, "playwright.config.ts")
        (r.ok if os.path.exists(cfg) else r.fail)("e2e-playwright", "config", "playwright.config.ts", "", "run /dev-infra:e2e-playwright")
        tests = [f for f in os.listdir(os.path.join(web, "e2e"))] if os.path.isdir(os.path.join(web, "e2e")) else []
        (r.ok if tests else r.fail)("e2e-playwright", "config", "e2e tests present", f"{len(tests)} file(s)")
        turbo = os.path.join(root, "turbo.json")
        has_task = os.path.exists(turbo) and "e2e" in json.load(open(turbo)).get("tasks", {})
        (r.ok if has_task else r.warn)("e2e-playwright", "config", "turbo e2e task", "", 'add "e2e": {"cache": false, ...}')
    if "runners" in active:
        runners = spec.get("ci", {}).get("runners", [])
        args = [sys.executable, os.path.join(os.path.dirname(__file__), "check_runners.py"),
                "--repo", spec["ci"]["github_repo"]] + sum([["--expect", f"{x['name']}:{','.join(x['labels'])}"] for x in runners], [])
        p = subprocess.run(args, capture_output=True, text=True)
        for line in p.stdout.splitlines():
            st, _, rest = line.partition(" ")
            r.add("runners", "cloud", rest.strip().split(":")[0], st.strip(), rest.strip())

    for m, s in statuses.items():
        if m not in active and s != "not used":
            r.skip(m, "-", "module", f"status: {s}")

    fails = sum(1 for x in r.rows if x["status"] == "FAIL")
    warns = sum(1 for x in r.rows if x["status"] == "WARN")
    if a.json:
        print(json.dumps({"failures": fails, "warnings": warns, "checks": r.rows}, indent=2))
    else:
        width = max(len(x["check"]) for x in r.rows) if r.rows else 10
        cur = None
        for x in r.rows:
            if x["module"] != cur:
                cur = x["module"]
                print(f"\n== {cur} ==")
            line = f"{x['status']:<5} {x['level']:<6} {x['check']:<{width}}  {x['detail']}"
            print(line.rstrip())
            if x["fix"] and x["status"] in ("FAIL", "WARN"):
                print(f"{'':<13}fix: {x['fix']}")
        print(f"\n{fails} failure(s), {warns} warning(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
