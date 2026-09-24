#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Tanner Golden
# SPDX-License-Identifier: MIT
"""Tests for the composite action's run body: the bash a consumer's
`uses: tannergolden/emblems@v1` step executes. The script and the identity
constants are lifted out of action.yml by indentation and by pattern rather
than parsed, so the suite needs no PyYAML, like the rest of the kit.

Every test renders into a throwaway consumer repository with a bare remote
behind it, so a push here is a real push."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "action.yml"
HOTLINK = "https://img.shields.io/badge/Build-OK-green?style=for-the-badge"


def run_body() -> str:
    """The `run: |` block of the one step, dedented."""
    lines = ACTION.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "run: |")
    indent = len(lines[start]) - len(lines[start].lstrip()) + 2
    body = []
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        body.append(line[indent:])
    return "\n".join(body) + "\n"


def step_env() -> dict[str, str]:
    """The literal KIT_* values the step's env block fixes: the identities."""
    found = dict(re.findall(r"^\s+(KIT_[A-Z_]+): '([^']*)'$",
                            ACTION.read_text(encoding="utf-8"), re.M))
    assert found, "no literal KIT_* env in action.yml"
    return found


SCRIPT = run_body()
IDENTITY = step_env()


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


class Consumer:
    """A repository the action renders FOR, with a bare remote to push to."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.remote = tmp / "remote.git"
        self.root = tmp / "work"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.root)], check=True)
        for k, v in (("user.name", "Consumer"), ("user.email", "consumer@example.com")):
            git(self.root, "config", k, v)
        (self.root / ".github").mkdir()
        (self.root / ".github" / "badges.yml").write_text(
            "badges:\n  - name: status\n    label: Status\n    message: Active\n"
            "    label_color: black\n    message_color: green\n", encoding="utf-8")
        (self.root / "README.md").write_text("# Widgets\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")
        git(self.root, "remote", "add", "origin", str(self.remote))
        git(self.root, "push", "-q", "-u", "origin", "main")

    def run(self, mode: str = "render", commit: str = "true", message: str = ""):
        """Run the action's script as Actions would: inputs through env."""
        out = self.tmp / "output.txt"
        out.write_text("", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
        env.update(IDENTITY)
        env.update({
            "KIT_MODE": mode, "KIT_DATA": ".github/badges.yml", "KIT_OUT": "assets/badges",
            "KIT_SET": "", "KIT_SEED": "", "KIT_PATH": str(ROOT),
            "KIT_COMMIT": commit, "KIT_MESSAGE": message,
            "GITHUB_WORKSPACE": str(self.root), "GITHUB_OUTPUT": str(out),
            "GITHUB_REPOSITORY": "acme/widgets", "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_RUN_ID": "42", "GITHUB_WORKFLOW": "Badges",
        })
        proc = subprocess.run(["bash", "-c", SCRIPT], cwd=self.root, env=env,
                              capture_output=True, text=True)
        outputs = dict(line.split("=", 1)
                       for line in out.read_text(encoding="utf-8").splitlines() if "=" in line)
        return proc, outputs

    def head(self) -> str:
        return git(self.root, "rev-parse", "HEAD")

    def remote_main(self) -> str:
        return git(self.remote, "rev-parse", "refs/heads/main")

    def committed_files(self) -> list[str]:
        return git(self.root, "show", "--name-only", "--format=", "HEAD").splitlines()


class Commit(unittest.TestCase):
    """`commit: true` commits the kit's output as the kit's author, and pushes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.c = Consumer(Path(self.tmp.name).resolve())

    def tearDown(self):
        self.tmp.cleanup()

    def assertRan(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_the_kit_author_authors_it_and_the_workflow_commits_it(self):
        proc, out = self.c.run()
        self.assertRan(proc)
        sha = self.c.head()
        self.assertEqual(out["changed"], "true")
        self.assertEqual(out["commit"], sha)
        self.assertEqual(git(self.c.root, "log", "-1", "--format=%an <%ae>"), IDENTITY["KIT_AUTHOR"])
        self.assertEqual(git(self.c.root, "log", "-1", "--format=%cn <%ce>"),
                         f"{IDENTITY['KIT_COMMITTER_NAME']} <{IDENTITY['KIT_COMMITTER_EMAIL']}>")
        self.assertEqual(git(self.c.root, "log", "-1", "--format=%s"),
                         "chore(badges): 🏷️ re-render badges")
        body = git(self.c.root, "log", "-1", "--format=%b")
        for needle in ("tannergolden/emblems", "mode render", ".github/badges.yml",
                       "assets/badges", '"Badges" workflow',
                       "https://github.com/acme/widgets/actions/runs/42"):
            self.assertIn(needle, body)
        self.assertIn("assets/badges/static/status.svg", self.c.committed_files())
        self.assertEqual(self.c.remote_main(), sha, "the commit was not pushed")
        self.assertEqual(git(self.c.root, "status", "--porcelain"), "")

    def test_the_author_is_the_repository_owner_by_noreply_address(self):
        # The identity GitHub resolves to the account, never a personal inbox.
        self.assertEqual(IDENTITY["KIT_AUTHOR"],
                         "Tanner Golden <24684994+tannergolden@users.noreply.github.com>")
        self.assertEqual(IDENTITY["KIT_COMMITTER_NAME"], "github-actions[bot]")
        self.assertTrue(IDENTITY["KIT_COMMITTER_EMAIL"].endswith("@users.noreply.github.com"))

    def test_a_clean_second_run_commits_nothing(self):
        self.c.run()
        before = self.c.head()
        proc, out = self.c.run()
        self.assertRan(proc)
        self.assertEqual(out["changed"], "false")
        self.assertEqual(out["commit"], "")
        self.assertEqual(self.c.head(), before)

    def test_check_mode_writes_nothing_even_when_asked_to_commit(self):
        self.c.run()
        before = self.c.head()
        proc, out = self.c.run(mode="check")
        self.assertRan(proc)
        self.assertEqual(out["commit"], "")
        self.assertEqual(self.c.head(), before)

    def test_commit_off_leaves_git_alone(self):
        before = self.c.head()
        proc, out = self.c.run(commit="false")
        self.assertRan(proc)
        self.assertEqual(out["changed"], "true")
        self.assertEqual(out["commit"], "")
        self.assertEqual(self.c.head(), before)
        self.assertEqual(self.c.remote_main(), before)
        self.assertIn("?? assets/", git(self.c.root, "status", "--porcelain"))

    def test_only_what_the_run_changed_is_committed(self):
        # A checkout already carrying edits keeps them: the commit is the
        # kit's output and nothing else.
        (self.c.root / "README.md").write_text("# Widgets\n\nedited\n", encoding="utf-8")
        (self.c.root / "scratch.txt").write_text("junk\n", encoding="utf-8")
        proc, _ = self.c.run()
        self.assertRan(proc)
        files = self.c.committed_files()
        self.assertTrue(files and all(f.startswith("assets/badges/") for f in files), files)
        status = git(self.c.root, "status", "--porcelain")
        self.assertRegex(status, r"(?m)^ ?M README\.md$")
        self.assertRegex(status, r"(?m)^\?\? scratch\.txt$")

    def test_the_subject_can_be_chosen(self):
        proc, _ = self.c.run(message="build: refresh the badges")
        self.assertRan(proc)
        self.assertEqual(git(self.c.root, "log", "-1", "--format=%s"), "build: refresh the badges")

    def test_localize_commits_the_rewritten_markdown_too(self):
        (self.c.root / "README.md").write_text(f"# Widgets\n\n![Build]({HOTLINK})\n",
                                               encoding="utf-8")
        git(self.c.root, "commit", "-q", "-a", "-m", "hotlink")
        proc, out = self.c.run(mode="localize")
        self.assertRan(proc)
        self.assertEqual(git(self.c.root, "log", "-1", "--format=%s"),
                         "chore(badges): 🏷️ localize shields.io badges")
        files = self.c.committed_files()
        self.assertIn("README.md", files)
        self.assertTrue(any(f.startswith("assets/badges/static/") for f in files), files)
        self.assertNotIn("img.shields.io", (self.c.root / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(self.c.remote_main(), out["commit"])

    def test_a_detached_checkout_is_refused_before_anything_is_pushed(self):
        before = self.c.head()
        git(self.c.root, "checkout", "-q", "--detach")
        proc, _ = self.c.run()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("::error::", proc.stdout)
        self.assertIn("branch", proc.stdout)
        self.assertEqual(self.c.remote_main(), before)


if __name__ == "__main__":
    unittest.main()
