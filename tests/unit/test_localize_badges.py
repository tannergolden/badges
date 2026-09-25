# SPDX-FileCopyrightText: 2026 Tanner Golden
# SPDX-License-Identifier: MIT
"""Tests for src/localize-badges.py: shields.io URL parsing, signature
dedupe, the rewrite and check passes, and the configurable badge tree."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[2] / "src"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SRC / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lb = load("localize_badges", "localize-badges.py")

FTB = "?style=for-the-badge"


def shields(label: str, message: str, color: str, query: str = FTB) -> str:
    return f"https://img.shields.io/badge/{label}-{message}-{color}{query}"


class ParseShields(unittest.TestCase):
    def test_basic_fields_and_house_icon(self):
        spec = lb.parse_shields(shields("Status", "Active", "2EA043"))
        self.assertEqual(spec["label"], "Status")
        self.assertEqual(spec["message"], "Active")
        self.assertEqual(spec["message_color"], "green")
        self.assertEqual(spec["label_color"], "black")
        self.assertEqual(spec["icon"], "pulse")
        self.assertEqual(spec["style"], "for-the-badge")

    def test_escaped_dash_and_underscore(self):
        spec = lb.parse_shields(shields("Code__Style", "Semi--Formal", "blue"))
        self.assertEqual(spec["label"], "Code_Style")
        self.assertEqual(spec["message"], "Semi-Formal")

    def test_underscore_becomes_space(self):
        spec = lb.parse_shields(shields("Last_Commit", "Today", "green"))
        self.assertEqual(spec["label"], "Last Commit")

    def test_unknown_hex_passes_through_and_shorthand_expands(self):
        self.assertEqual(lb.parse_shields(shields("A", "B", "123456"))["message_color"], "#123456")
        self.assertEqual(lb.parse_shields(shields("A", "B", "abc"))["message_color"], "#ABC")

    def test_named_colors_map_to_tokens(self):
        for raw, tok in (("brightgreen", "green"), ("critical", "red"),
                         ("informational", "blue"), ("lightgrey", "slate")):
            self.assertEqual(lb.parse_shields(shields("A", "B", raw))["message_color"], tok, raw)

    def test_style_mapping(self):
        # plastic used to flatten, because the kit could not draw it. It can
        # now, so a migration keeps the shape it had. social has no equivalent
        # chip here, so it still lands on flat.
        for raw, style in (("plastic", "plastic"), ("social", "flat"),
                           ("flat-square", "flat-square")):
            spec = lb.parse_shields(shields("A", "B", "blue", f"?style={raw}"))
            self.assertEqual(spec["style"], style, raw)
        self.assertEqual(lb.parse_shields(shields("A", "B", "blue", ""))["style"], "flat")

    def test_label_color_query(self):
        spec = lb.parse_shields(shields("A", "B", "green", FTB + "&labelColor=C0A062"))
        self.assertEqual(spec["label_color"], "gold")

    def test_non_static_endpoint_is_left_alone(self):
        self.assertIsNone(lb.parse_shields("https://img.shields.io/github/stars/o/r"))
        self.assertIsNone(lb.parse_shields("https://img.shields.io/badge/onlyone"))


class Naming(unittest.TestCase):
    def test_signature_ignores_nothing_that_changes_the_drawing(self):
        a = lb.parse_shields(shields("A", "B", "green"))
        b = lb.parse_shields(shields("A", "B", "red"))
        self.assertNotEqual(lb._signature(a), lb._signature(b))
        self.assertEqual(lb._signature(a), lb._signature(lb.parse_shields(shields("A", "B", "green"))))

    def test_base_slug_is_kebab(self):
        spec = lb.parse_shields(shields("Code_Style", "PEP_8!", "blue"))
        self.assertEqual(lb._base_slug(spec), "code-style-pep-8")


class Repo(unittest.TestCase):
    """The rewrite and check passes, on a real git repository."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for k, v in (("user.email", "t@e.com"), ("user.name", "T")):
            subprocess.run(["git", "-C", str(self.root), "config", k, v], check=True)
        (self.root / ".github").mkdir()
        (self.root / ".github" / "badges.yml").write_text(
            "badges:\n  - name: own\n    label: Own\n    message: Badge\n", encoding="utf-8")
        # Identity from the Actions env, no workspace/ref leaking in from the
        # session running these tests.
        env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
        env["GITHUB_REPOSITORY"] = "acme/widgets"
        self._env = mock.patch.dict(os.environ, env, clear=True)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self.tmp.cleanup()

    def write(self, rel: str, text: str) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def track(self):
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)

    def run_cli(self, *extra: str) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = lb.main(["--root", str(self.root), *extra])
        return code, buf.getvalue()

    def test_identical_badges_share_one_file_and_get_absolute_urls(self):
        url = shields("Status", "Active", "2EA043")
        for f in ("docs/A.md", "docs/B.md", "docs/C.md"):
            self.write(f, f"# x\n![Status]({url})\n")
        self.track()
        code, out = self.run_cli()
        self.assertEqual(code, 0, out)
        static = self.root / "assets" / "badges" / "static"
        self.assertEqual([p.name for p in static.glob("*.svg")], ["status-active.svg"])
        expect = "https://raw.githubusercontent.com/acme/widgets/main/assets/badges/static/status-active.svg"
        for f in ("docs/A.md", "docs/B.md", "docs/C.md"):
            self.assertIn(expect, (self.root / f).read_text(encoding="utf-8"), f)

    def test_slug_collision_gets_a_hash_suffix(self):
        self.write("docs/A.md", f"![a]({shields('Build', 'OK', 'green')})\n"
                                f"![b]({shields('Build', 'OK', 'red')})\n")
        self.track()
        self.assertEqual(self.run_cli()[0], 0)
        names = sorted(p.name for p in (self.root / "assets/badges/static").glob("*.svg"))
        self.assertEqual(len(names), 2)
        self.assertTrue(all(n.startswith("build-ok-") for n in names), names)

    def test_custom_out_dir_is_used_everywhere(self):
        self.write("docs/A.md", f"![x]({shields('Docs', 'Live', 'blue')})\n")
        self.track()
        code, out = self.run_cli("--out", "images/marks")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.root / "images/marks/static/docs-live.svg").is_file())
        text = (self.root / "docs/A.md").read_text(encoding="utf-8")
        self.assertIn("/acme/widgets/main/images/marks/static/docs-live.svg", text)
        self.assertNotIn("assets/badges", text)
        # And the check pass recognises the custom tree as current.
        self.assertEqual(self.run_cli("--out", "images/marks", "--check")[0], 0)

    def test_root_readme_keeps_relative_refs_to_own_badges(self):
        self.write("README.md", "![Own](assets/badges/static/own.svg)\n")
        self.write("docs/A.md", "![Own](../assets/badges/static/own.svg)\n")
        self.track()
        self.assertEqual(self.run_cli()[0], 0)
        self.assertIn("(assets/badges/static/own.svg)", (self.root / "README.md").read_text())
        # A badge from badges.yml is the kit's own: never rewritten, anywhere.
        self.assertIn("(../assets/badges/static/own.svg)", (self.root / "docs/A.md").read_text())

    def test_check_fails_on_a_remaining_hotlink_then_passes(self):
        self.write("docs/A.md", f"![x]({shields('A', 'B', 'blue')})\n")
        self.track()
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("img.shields.io", out)
        self.assertEqual(self.run_cli()[0], 0)
        self.assertEqual(self.run_cli("--check")[0], 0)

    def test_check_flags_a_relative_doc_badge_outside_the_readme(self):
        self.write("docs/A.md", "![x](../assets/badges/static/nope.svg)\n")
        self.track()
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("RELATIVE", out)

    def test_untouched_second_pass_changes_nothing(self):
        self.write("docs/A.md", f"![x]({shields('A', 'B', 'blue')})\n")
        self.track()
        self.run_cli()
        before = (self.root / "docs/A.md").read_bytes()
        _, out = self.run_cli()
        self.assertEqual((self.root / "docs/A.md").read_bytes(), before)
        self.assertIn("across 0 file(s)", out)


class Configure(unittest.TestCase):
    def test_out_outside_repo_falls_back_to_conventional_rel(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            lb.configure(root=a, out=b)
            self.assertEqual(lb.OUT_REL, "assets/badges")
            lb.configure(root=a, out="images/marks")
            self.assertEqual(lb.OUT_REL, "images/marks")
            self.assertTrue(lb._DOC_REF_RE.search("../images/marks/static/x.svg"))
            self.assertFalse(lb._DOC_REF_RE.search("../assets/badges/static/x.svg"))
        lb.configure()  # leave the module as it was imported


if __name__ == "__main__":
    unittest.main()
