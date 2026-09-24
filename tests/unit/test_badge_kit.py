# SPDX-FileCopyrightText: 2026 Tanner Golden
# SPDX-License-Identifier: MIT
"""Behavioural tests for src/badge-kit.py beyond its built-in self-test:
folder routing, the CLI's --set/--check/--markdown paths, and pruning."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SRC / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bk = load("badge_kit", "badge-kit.py")

DATA = """badges:
  - name: status
    label: Status
    message: Active
    message_color: green
    icon: pulse
    link: ./
  - name: score
    label: Score
    message: 'a:b'
    label_color: '#C0A062'
    message_color: green
"""


def run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = bk.main(argv)
    return code, buf.getvalue()


class Routing(unittest.TestCase):
    def test_gold_token_is_dynamic(self):
        self.assertEqual(bk._dir_for({"label_color": "gold"}), "dynamic")

    def test_gold_hex_is_dynamic_in_either_case(self):
        for hexc in ("#C0A062", "#c0a062"):
            self.assertEqual(bk._dir_for({"label_color": hexc}), "dynamic", hexc)

    def test_black_and_its_hex_are_static(self):
        for lc in ("black", "#000000", None):
            self.assertEqual(bk._dir_for({"label_color": lc}), "static", lc)

    def test_validate_and_routing_agree_on_hex_gold(self):
        # A hex-gold label is a health badge everywhere: validate() applies the
        # traffic-light rule to it, and the renderer files it under dynamic/.
        bad = dict(name="x", label="A", message="B", label_color="#C0A062", message_color="blue")
        self.assertTrue(bk.validate([bad]))
        self.assertEqual(bk._dir_for(bad), "dynamic")


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".github").mkdir()
        self.data = self.root / ".github" / "badges.yml"
        self.data.write_text(DATA, encoding="utf-8")
        self.out = self.root / "assets" / "badges"

    def tearDown(self):
        self.tmp.cleanup()

    def render(self, *extra: str) -> tuple[int, str]:
        return run(["--root", str(self.root), *extra])

    def test_defaults_derive_from_root(self):
        code, _ = self.render()
        self.assertEqual(code, 0)
        self.assertTrue((self.out / "static" / "status.svg").is_file())
        self.assertTrue((self.out / "dynamic" / "score.svg").is_file(),
                        "hex-gold label must land in dynamic/")

    def test_markdown_wraps_link_and_keeps_casing(self):
        code, out = self.render("--markdown")
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(lines[0], "[![Status: Active](assets/badges/static/status.svg)](./)")
        # No link: a bare image, and the dynamic folder for the gold label.
        self.assertEqual(lines[1], "![Score: a:b](assets/badges/dynamic/score.svg)")
        self.assertFalse(self.out.exists(), "--markdown must write nothing")

    def test_set_keeps_a_colon_that_is_not_a_color(self):
        code, _ = self.render("--set", "score=1:2")
        self.assertEqual(code, 0)
        entry = next(b for b in bk.load_badges(self.data) if b["name"] == "score")
        self.assertEqual(entry["message"], "1:2")
        self.assertEqual(entry["message_color"], "green")

    def test_set_splits_a_real_color_suffix(self):
        code, _ = self.render("--set", "status=Paused:yellow")
        self.assertEqual(code, 0)
        entry = next(b for b in bk.load_badges(self.data) if b["name"] == "status")
        self.assertEqual((entry["message"], entry["message_color"]), ("Paused", "yellow"))

    def test_set_unknown_name_fails(self):
        code, out = self.render("--set", "nope=x")
        self.assertEqual(code, 1)
        self.assertIn("no entry named nope", out)

    def test_check_passes_then_detects_drift(self):
        self.render()
        self.assertEqual(self.render("--check")[0], 0)
        (self.out / "static" / "status.svg").write_text("<svg/>", encoding="utf-8")
        code, out = self.render("--check")
        self.assertEqual(code, 1)
        self.assertIn("static/status", out)

    def test_check_tolerates_another_kit_version(self):
        self.render()
        svg = (self.out / "static" / "status.svg")
        svg.write_text(svg.read_text(encoding="utf-8").replace(
            f"badge-kit v{bk.KIT_VERSION}", "badge-kit v0"), encoding="utf-8")
        code, out = self.render("--check")
        self.assertEqual(code, 0, "a version difference is a notice, not a failure")
        self.assertIn("another kit version", out)

    def test_render_prunes_an_orphan(self):
        self.render()
        orphan = self.out / "static" / "gone.svg"
        orphan.write_text("<svg/>", encoding="utf-8")
        self.render()
        self.assertFalse(orphan.exists())

    def test_missing_data_is_error_but_check_skips(self):
        self.data.unlink()
        self.assertEqual(self.render()[0], 1)
        self.assertEqual(self.render("--check")[0], 0)


if __name__ == "__main__":
    unittest.main()


class Gallery(unittest.TestCase):
    """The gallery is generated from the registries, so it cannot drift."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".github").mkdir()
        (self.root / ".github" / "badges.yml").write_text(DATA, encoding="utf-8")
        self.out = self.root / "assets" / "badges"
        self.page = self.root / "docs" / "Gallery.md"

    def tearDown(self):
        self.tmp.cleanup()

    def gallery(self, *extra: str) -> tuple[int, str]:
        return run(["--root", str(self.root), "--gallery", *extra])

    def test_one_badge_per_registry_entry(self):
        self.assertEqual(self.gallery()[0], 0)
        rendered = {p.name for p in (self.out / "static").glob("gallery-*.svg")}
        self.assertEqual(rendered, bk.gallery_filenames())
        # Every icon and every token is present, not a hand-picked subset.
        for name in bk.ICONS:
            self.assertIn(f"gallery-icon-{name}.svg", rendered, name)
        for tok in bk.PALETTE:
            self.assertIn(f"gallery-color-{tok}.svg", rendered, tok)

    def test_page_names_every_icon_and_token(self):
        self.gallery()
        text = self.page.read_text(encoding="utf-8")
        for name in bk.ICONS:
            self.assertIn(f"gallery-icon-{name}.svg", text, name)
        for tok in bk.PALETTE:
            self.assertIn(f"gallery-color-{tok}.svg", text, tok)
        # Generated, and says so, so nobody hand-edits it.
        self.assertIn("GENERATED BY src/badge-kit.py --gallery", text)

    def test_check_passes_then_catches_drift_in_badge_and_page(self):
        self.gallery()
        self.assertEqual(self.gallery("--check")[0], 0)
        (self.out / "static" / "gallery-icon-rocket.svg").write_text("<svg/>", encoding="utf-8")
        code, out = self.gallery("--check")
        self.assertEqual(code, 1)
        self.assertIn("gallery-icon-rocket.svg", out)
        self.gallery()
        self.page.write_text("stale", encoding="utf-8")
        code, out = self.gallery("--check")
        self.assertEqual(code, 1)
        self.assertIn("Gallery.md is out of date", out)

    def test_a_dropped_registry_entry_is_pruned(self):
        self.gallery()
        orphan = self.out / "static" / "gallery-icon-nolongerreal.svg"
        orphan.write_text("<svg/>", encoding="utf-8")
        self.gallery()
        self.assertFalse(orphan.exists())

    def test_render_does_not_prune_the_gallery(self):
        # The gallery shares static/ but is not in the data file. Without the
        # reservation, a plain render would delete all 111 as orphans.
        self.gallery()
        code, _ = run(["--root", str(self.root)])
        self.assertEqual(code, 0)
        survivors = {p.name for p in (self.out / "static").glob("gallery-*.svg")}
        self.assertEqual(survivors, bk.gallery_filenames())

    def test_health_gallery_only_uses_legal_colors(self):
        for stem, kw in bk.gallery_specs():
            if stem.startswith("gallery-health-"):
                self.assertEqual(
                    bk.validate([dict(name="x", **{k: v for k, v in kw.items() if v is not None})]),
                    [], stem)


class Palette(unittest.TestCase):
    """The palette is a designed family, not a bag of hexes."""

    @staticmethod
    def distance(a: str, b: str) -> float:
        ar, ag, ab = (int(a[i:i + 2], 16) for i in (1, 3, 5))
        br, bg, bb = (int(b[i:i + 2], 16) for i in (1, 3, 5))
        rm = (ar + br) / 2
        return (((2 + rm / 256) * (ar - br) ** 2) + 4 * (ag - bg) ** 2
                + ((2 + (255 - rm) / 256) * (ab - bb) ** 2)) ** 0.5

    def test_one_token_per_icon(self):
        self.assertEqual(len(bk.PALETTE), len(bk.ICONS))

    def test_every_value_is_a_six_digit_hex(self):
        for tok, hexc in bk.PALETTE.items():
            self.assertRegex(hexc, r"^#[0-9A-F]{6}$", tok)

    def test_no_two_tokens_read_as_the_same_color(self):
        # 30.0 is just under the spacing the palette already had before it was
        # extended (gold vs tan). A new token closer than that to an existing
        # one is a duplicate a user cannot tell apart by eye.
        import itertools
        for a, b in itertools.combinations(bk.PALETTE, 2):
            d = self.distance(bk.PALETTE[a], bk.PALETTE[b])
            self.assertGreaterEqual(d, 30.0, f"{a} and {b} are indistinguishable (d={d:.1f})")

    def test_health_colors_are_all_real_tokens(self):
        for tok in bk.HEALTH_COLORS | bk.HEALTH_NEUTRAL:
            self.assertIn(tok, bk.PALETTE, tok)

    def test_random_pool_excludes_every_reserved_token(self):
        pool = set(bk.STATIC_RANDOM_POOL)
        for tok in bk.HEALTH_COLORS | bk.HEALTH_NEUTRAL | {"black", "gold", "white", "pink", "purple"}:
            self.assertNotIn(tok, pool, tok)


class GalleryLayout(unittest.TestCase):
    """Grouping has to stay total: every icon and token placed exactly once."""

    def test_every_icon_is_grouped_exactly_once(self):
        seen = [i for _, group in bk.ICON_GROUPS for i in group]
        self.assertEqual(len(seen), len(set(seen)), "an icon is in two groups")
        for name in seen:
            self.assertIn(name, bk.ICONS, f"{name} is grouped but not in ICONS")

    def test_an_ungrouped_icon_still_reaches_the_page(self):
        # The catch-all is what makes ICON_GROUPS safe to leave alone when a
        # glyph is added, so it must actually work.
        original = bk.ICON_GROUPS
        try:
            bk.ICON_GROUPS = tuple((t, tuple(i for i in g if i != "rocket"))
                                   for t, g in original)
            md = bk.gallery_markdown("../assets/badges")
            self.assertIn("Everything else", md)
            self.assertIn("gallery-icon-rocket.svg", md)
        finally:
            bk.ICON_GROUPS = original

    def test_every_token_lands_in_exactly_one_family(self):
        placed = [t for _, toks in bk.color_families() for t in toks]
        self.assertEqual(sorted(placed), sorted(bk.PALETTE))

    def test_families_are_ordered_so_a_row_reads_as_a_gradient(self):
        for name, toks in bk.color_families():
            if name == "Neutrals":
                lums = [bk._hue_sat_lum(bk.PALETTE[t])[2] for t in toks]
                self.assertEqual(lums, sorted(lums), name)
            else:
                lo, hi = next((l, h) for n, l, h in bk.COLOR_BANDS if n == name)
                keys = []
                for tok in toks:
                    h = bk._hue_sat_lum(bk.PALETTE[tok])[0]
                    keys.append(h - 360.0 if (lo > hi and h >= lo) else h)
                self.assertEqual(keys, sorted(keys), name)


class Styles(unittest.TestCase):
    """Every style has to be a complete, legal geometry."""

    def test_every_style_declares_every_geometry_key(self):
        keys = set(bk.STYLES["for-the-badge"])
        for name, g in bk.STYLES.items():
            self.assertEqual(set(g), keys, f"{name} is missing or has extra keys")

    def test_corner_radius_never_exceeds_half_the_height(self):
        # SVG silently clamps a larger rx, so the badge would not be the shape
        # the style claims.
        for name, g in bk.STYLES.items():
            self.assertLessEqual(g["rx"], g["h"] / 2 + 1e-9, name)

    def test_every_sheen_is_a_real_gradient(self):
        for name, g in bk.STYLES.items():
            if g["sheen"] is not None:
                self.assertIn(g["sheen"], bk.SHEENS, name)

    def test_rounding_and_sheen_are_independent(self):
        # The pair used to be one `deco` flag. Splitting them is only worth
        # anything if both combinations that flag could not express exist.
        combos = {(bool(g["rx"]), bool(g["sheen"])) for g in bk.STYLES.values()}
        self.assertIn((True, False), combos, "no rounded-but-flat style")
        self.assertIn((False, False), combos, "no square-and-flat style")
        self.assertIn((True, True), combos, "no rounded-and-sheened style")

    def test_a_scaled_style_measures_proportionally(self):
        # compact renders at 9px from tables measured at 11px. Its text run
        # must be 9/11 of the same run at 11px, not an approximation.
        word = "Passing"
        norm = bk._text_width(word, bk._W_NORM11, 9.0, 0.0)
        small = bk.STYLES["compact"]
        scaled = bk._text_width(word, small["table"], small["fallback"], 0.0) * small["mscale"]
        self.assertAlmostEqual(scaled, norm * (9 / 11), places=6)

    def test_letter_spacing_is_not_scaled_with_the_face(self):
        # ls is a final-pixel value: scaling it with the face would compound.
        # Asserted against a temporary style rather than a real one, so the
        # invariant survives any style being added or removed.
        probe = dict(bk.STYLES["compact"], ls=1.3, mscale=14 / 11, fs=14)
        bk.STYLES["probe"] = probe
        try:
            svg = bk.render("AB", "CD", "black", "green", None, "probe")
            self.assertIn('letter-spacing="1.3"', svg)
        finally:
            del bk.STYLES["probe"]

    def test_all_styles_render_well_formed_and_deterministically(self):
        import xml.dom.minidom as minidom
        for name in bk.STYLES:
            svg = bk.render("Build Status", "Passing", "black", "green", "check", name)
            minidom.parseString(svg)
            self.assertEqual(svg, bk.render("Build Status", "Passing", "black",
                                            "green", "check", name), name)

    def test_the_codemod_keeps_a_plastic_hotlink_plastic(self):
        lb = load("localize_badges_styles", "localize-badges.py")
        spec = lb.parse_shields(
            "https://img.shields.io/badge/A-B-blue?style=plastic")
        self.assertEqual(spec["style"], "plastic")
        self.assertIn("plastic", bk.STYLES)


class StyleGrouping(unittest.TestCase):
    """Styles are organised by the job you pick them for, not by age."""

    def test_every_style_is_grouped_exactly_once(self):
        seen = [s for _, _, group in bk.STYLE_GROUPS for s in group]
        self.assertEqual(len(seen), len(set(seen)), "a style is in two groups")
        self.assertEqual(sorted(seen), sorted(bk.STYLES))

    def test_the_default_is_listed_first(self):
        # The dict order is the gallery's order and the order the error
        # messages print, so the default has to lead.
        self.assertEqual(next(iter(bk.STYLES)), bk.DEFAULT_STYLE)
        self.assertEqual(bk.STYLE_GROUPS[0][2][0], bk.DEFAULT_STYLE)

    def test_every_group_has_a_blurb_saying_what_it_is_for(self):
        for title, blurb, _ in bk.STYLE_GROUPS:
            self.assertTrue(blurb.strip(), f"{title} has no description")

    def test_an_ungrouped_style_still_reaches_the_page(self):
        original = bk.STYLE_GROUPS
        try:
            bk.STYLE_GROUPS = tuple(
                (t, b, tuple(s for s in g if s != "pill")) for t, b, g in original)
            md = bk.gallery_markdown("../assets/badges")
            self.assertIn("Everything else", md)
            self.assertIn("gallery-style-pill.svg", md)
        finally:
            bk.STYLE_GROUPS = original

    def test_groups_are_internally_consistent(self):
        by_name = {t: g for t, _, g in bk.STYLE_GROUPS}
        # Headline means caps; nothing else does.
        for s in by_name["Headline"]:
            self.assertTrue(bk.STYLES[s]["caps"], f"{s} is headline but not caps")
        for s in by_name["Standard"] + by_name["Dense"]:
            self.assertFalse(bk.STYLES[s]["caps"], f"{s} is not headline but caps")
        # Dense is shorter than every standard chip, which is the whole point.
        tallest_dense = max(bk.STYLES[s]["h"] for s in by_name["Dense"])
        shortest_standard = min(bk.STYLES[s]["h"] for s in by_name["Standard"])
        self.assertLess(tallest_dense, shortest_standard)


class Combinations(unittest.TestCase):
    """The headline number in the README is counted, and stays counted."""

    def setUp(self):
        self.counts = bk.combination_count()
        self.readme = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")

    def test_the_arithmetic_holds(self):
        c = self.counts
        self.assertEqual(c["total"], c["pairs"] * c["icons"] * c["styles"])
        self.assertEqual(c["total"], c["static"] + c["health"])
        self.assertEqual(c["pairs"] + c["refused"], len(bk.PALETTE) ** 2)
        self.assertEqual(c["icons"], len(bk.ICONS) + 1)
        self.assertEqual(c["styles"], len(bk.STYLES))

    def test_refusals_are_exactly_the_traffic_light_rule(self):
        # A gold label has len(HEALTH) legal partners instead of the whole
        # palette; nothing else is refused.
        legal = len(bk.HEALTH_COLORS | bk.HEALTH_NEUTRAL)
        self.assertEqual(self.counts["refused"], len(bk.PALETTE) - legal)
        self.assertEqual(self.counts["health"],
                         legal * self.counts["icons"] * self.counts["styles"])

    def test_the_readme_states_the_counted_number(self):
        # The registries grew from 40 tokens and 3 styles this year, so a
        # hand-typed total would already be wrong. This is the guard.
        for key in ("total", "static", "health", "pairs"):
            self.assertTrue(
                f"{self.counts[key]:,}" in self.readme,
                f"README does not state the counted {key} "
                f"({self.counts[key]:,}); re-run `make gallery` and update it")
        self.assertTrue(
            f"refuses {self.counts['refused']} of those" in self.readme,
            f"README does not state that {self.counts['refused']} pairs are refused")

    def test_the_gallery_states_it_too(self):
        md = bk.gallery_markdown("../assets/badges")
        self.assertIn(f"{self.counts['total']:,}", md)
