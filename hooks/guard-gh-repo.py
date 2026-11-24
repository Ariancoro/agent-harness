#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block `gh` writes to a repository other than `origin`.

In a fork, `gh` resolves the default repository to the parent (the `upstream`
remote) when no default is set, so `gh pr create` or `gh issue create` can land
in somebody else's repository. This hook resolves the repository each `gh`
write would target and blocks it (exit code 2) when it differs from the
repository of the `origin` remote.

Set FORJA_ALLOW_FOREIGN_GH_REPO=1 in your own shell to disable it on purpose.
"""

import json
import os
import re
import shlex
import subprocess
import sys

WRITE_VERBS = {
    "pr": {"create", "edit", "merge", "close", "reopen", "comment", "review", "ready", "lock", "unlock"},
    "issue": {"create", "edit", "close", "reopen", "comment", "delete", "transfer", "develop", "lock", "unlock", "pin", "unpin"},
    "release": {"create", "edit", "delete", "upload", "delete-asset"},
    "label": {"create", "edit", "delete", "clone"},
    "repo": {"edit", "delete", "archive", "unarchive", "rename"},
    "secret": {"set", "delete"},
    "variable": {"set", "delete"},
    "workflow": {"run", "enable", "disable"},
    "run": {"rerun", "cancel", "delete"},
    "cache": {"delete"},
}
SEPARATORS = {"&&", "||", ";", "|", "&", "(", ")", "\n"}
GITHUB_REPO = re.compile(r"github\.com[:/]+([^/\s]+)/([^/\s#?]+?)(?:\.git)?(?:[/#?]|$)")


def repo_of_url(url):
    match = GITHUB_REPO.search(url)
    return f"{match.group(1)}/{match.group(2)}" if match else None


def run(args, cwd):
    try:
        out = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def segments(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    current = []
    try:
        for token in lexer:
            if token in SEPARATORS or set(token) <= set("&|;()"):
                if current:
                    yield current
                current = []
            else:
                current.append(token)
    except ValueError:
        return
    if current:
        yield current


def option_value(args, *names):
    for i, arg in enumerate(args):
        for name in names:
            if arg == name and i + 1 < len(args):
                return args[i + 1]
            if name.startswith("--") and arg.startswith(name + "="):
                return arg.split("=", 1)[1]
            if not name.startswith("--") and arg.startswith(name) and len(arg) > len(name):
                return arg[len(name):]
    return None


def api_target(args):
    """Return (is_write, explicit_repo, uses_default) for `gh api` args."""
    method = (option_value(args, "-X", "--method") or "").upper()
    has_fields = any(
        a in ("-f", "-F", "--field", "--raw-field", "--input") or a.startswith(("--field=", "--raw-field=", "--input="))
        for a in args
    )
    if not method:
        method = "POST" if has_fields else "GET"
    if method == "GET":
        return False, None, False
    path = next((a for a in args if not a.startswith("-") and a.startswith(("repos/", "/repos/"))), None)
    if path is None:
        return True, None, False
    parts = path.lstrip("/").split("/")
    if len(parts) < 3:
        return True, None, False
    owner, repo = parts[1], parts[2]
    if owner in ("{owner}", ":owner") or repo in ("{repo}", ":repo"):
        return True, None, True
    return True, f"{owner}/{repo}", False


def targets(tokens):
    """Yield (description, explicit_repo or None) for each gh write in a segment."""
    env_repo = None
    i = 0
    while i < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
        if tokens[i].startswith("GH_REPO="):
            env_repo = tokens[i].split("=", 1)[1]
        i += 1
    while i < len(tokens) and tokens[i] in ("env", "command", "exec", "time", "sudo", "nohup"):
        i += 1
    if i >= len(tokens) or os.path.basename(tokens[i]) != "gh":
        return
    args = tokens[i + 1:]
    if not args:
        return
    sub = args[0]
    explicit = option_value(args, "-R", "--repo") or env_repo
    if sub == "api":
        is_write, api_repo, uses_default = api_target(args[1:])
        if not is_write or (api_repo is None and not uses_default):
            return
        yield "gh api (write)", api_repo or explicit
        return
    if len(args) < 2 or args[1] not in WRITE_VERBS.get(sub, ()):
        return
    url_repo = next((repo_of_url(a) for a in args[2:] if "github.com/" in a and repo_of_url(a)), None)
    yield f"gh {sub} {args[1]}", explicit or url_repo


def main():
    if os.environ.get("FORJA_ALLOW_FOREIGN_GH_REPO") == "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    if not re.search(r"(^|[\s;&|(/])gh\s", command):
        return 0
    cwd = data.get("cwd") or os.getcwd()

    writes = [t for seg in segments(command) for t in targets(seg)]
    if not writes:
        return 0

    origin_url = run(["git", "remote", "get-url", "origin"], cwd)
    origin = repo_of_url(origin_url) if origin_url else None
    if not origin:
        return 0

    default = None
    for action, repo in writes:
        if repo is None:
            if default is None:
                default = os.environ.get("GH_REPO") or run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], cwd) or ""
            repo = default
        if repo and repo.lower() != origin.lower():
            print(
                f"Blocked by Forja: `{action}` would write to {repo}, but the origin of this clone is {origin}.\n"
                f"Pass `--repo {origin}` on every gh write, or run `gh repo set-default {origin}` once.\n"
                f"If writing to {repo} is intended, ask the user to run the command themselves.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
