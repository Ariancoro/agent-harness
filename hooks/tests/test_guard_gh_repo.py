"""Tests of hooks/guard-gh-repo.py. Run: python3 -m unittest discover -s hooks/tests"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guard-gh-repo.py"
OURS = "Ariancoro/agent-harness"
PARENT = "CodelyTV/agent-harness"


class GuardGhRepoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.clone = cls.tmp.name
        subprocess.run(["git", "init", "-q", cls.clone], check=True)
        subprocess.run(["git", "-C", cls.clone, "remote", "add", "origin", f"https://github.com/{OURS}.git"], check=True)
        subprocess.run(["git", "-C", cls.clone, "remote", "add", "upstream", f"git@github.com:{PARENT}.git"], check=True)
        cls.no_origin = tempfile.TemporaryDirectory()
        subprocess.run(["git", "init", "-q", cls.no_origin.name], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.no_origin.cleanup()

    def run_hook(self, command, default_repo=PARENT, cwd=None):
        # GH_REPO stands in for the repository gh resolves by default, with no network.
        env = {k: v for k, v in os.environ.items() if k not in ("GH_REPO", "FORJA_ALLOW_FOREIGN_GH_REPO")}
        env["GH_REPO"] = default_repo
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd or self.clone})
        result = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, env=env)
        return result.returncode

    def assertBlocked(self, command, **kwargs):
        self.assertEqual(self.run_hook(command, **kwargs), 2, command)

    def assertAllowed(self, command, **kwargs):
        self.assertEqual(self.run_hook(command, **kwargs), 0, command)

    def test_blocks_a_write_that_resolves_to_the_parent(self):
        self.assertBlocked('gh pr create --title "feat: x" --body-file /tmp/b.md')
        self.assertBlocked("gh issue create --title x --body y")

    def test_allows_a_write_with_the_origin_repo(self):
        self.assertAllowed(f'gh pr create --repo {OURS} --title "feat: x"')
        self.assertAllowed(f"gh pr create -R {OURS} --title x")
        self.assertAllowed(f"gh pr create --repo={OURS} --title x")
        self.assertAllowed('gh pr create --title "feat: x"', default_repo=OURS)

    def test_blocks_an_explicit_foreign_repo(self):
        self.assertBlocked(f"gh pr create --repo {PARENT} --title x", default_repo=OURS)
        self.assertBlocked(f"GH_REPO={PARENT} gh issue create --title x", default_repo=OURS)

    def test_blocks_a_url_of_the_parent(self):
        self.assertBlocked(f"gh issue comment https://github.com/{PARENT}/issues/3 --body hi", default_repo=OURS)

    def test_allows_reads(self):
        self.assertAllowed("gh pr list")
        self.assertAllowed("gh issue view 3")
        self.assertAllowed(f"gh api repos/{PARENT}/pulls")
        self.assertAllowed("gh api repos/{owner}/{repo}/issues/1 --jq .id")

    def test_checks_api_writes(self):
        self.assertBlocked('gh api --method POST repos/{owner}/{repo}/issues/1/sub_issues -F sub_issue_id="$id"')
        self.assertBlocked(f"gh api repos/{PARENT}/issues -f title=x", default_repo=OURS)
        self.assertAllowed(f"gh api -X POST repos/{OURS}/issues -f title=x")

    def test_checks_every_command_of_a_chain(self):
        self.assertBlocked(f"git push -u origin HEAD && gh pr create --title x")
        self.assertAllowed(f"git push -u origin HEAD && gh pr create --repo {OURS} --title x")

    def test_ignores_gh_that_is_not_the_command(self):
        self.assertAllowed('echo gh pr create')
        self.assertAllowed('git commit -m "docs: explain gh pr create"')

    def test_allows_everything_without_a_github_origin(self):
        self.assertAllowed("gh pr create --title x", cwd=self.no_origin.name)

    def test_can_be_disabled_by_the_user(self):
        env = dict(os.environ, GH_REPO=PARENT, FORJA_ALLOW_FOREIGN_GH_REPO="1")
        payload = json.dumps({"tool_input": {"command": "gh pr create --title x"}, "cwd": self.clone})
        result = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
