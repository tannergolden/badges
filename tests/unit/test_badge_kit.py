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


PLATES = """badges:
  - name: status
    label: Status
    message: Active
    icon: pulse
    style: blueprint-flat
    print: greenprint
    link: ./
  - name: build
    label: Build
    message: Passing
    label_color: gold
    message_color: green
    style: blueprint-for-the-badge
    reserve: [Failing, Pending]
"""


GOLD = '{"goldprint": {"label": "Goldprint", "line": "#B8860B", "ink": "#5C4400", "sheet": "#7A5B00"}}'


class Themes(unittest.TestCase):
    """The prints are data: the kit's own catalog, and a repository's own in .github/themes.json."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".github").mkdir()
        self.addCleanup(bk.use_themes, None)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text: str) -> None:
        (self.root / ".github" / "themes.json").write_text(text, encoding="utf-8")

    def test_the_catalog_is_the_eleven_prints_in_the_banners_order(self):
        import json
        catalog = json.loads(bk.THEMES_CATALOG.read_text(encoding="utf-8"))
        self.assertEqual((list(catalog), len(catalog)), (list(bk.BUILTIN), 11))
        self.assertEqual(list(bk.SPECTRUM), list(catalog)[:9], "the spectrum is the catalog's first nine")
        for name, spec in catalog.items():
            self.assertEqual(bk.theme_errors("x" + name, spec), [], name)
            self.assertTrue(all(v in bk.PALETTE for k, v in spec.items() if k != "label"), f"{name} is in tokens")

    def test_a_theme_in_hex_draws_a_plate_in_its_colours_by_day_and_by_night(self):
        self.write(GOLD)
        self.assertEqual(bk.use_themes(self.root), ("goldprint",))
        plate = dict(name="x", label="A", message="B", style="blueprint-flat", print="goldprint")
        self.assertEqual(bk.validate([plate]), [])
        files = bk.files_for(plate)
        self.assertIn('stroke="#B8860B"', files["static/x.svg"])
        self.assertIn('fill="#5C4400"', files["static/x.svg"])
        self.assertIn('fill="#7A5B00"', files["static/x-dark.svg"])
        self.assertIn('fill="#FFFFFF"', files["static/x-dark.svg"], "lettered in white when night is left out")

    def test_a_theme_in_tokens_draws_exactly_as_the_same_tokens_would(self):
        self.write('{"navyprint": {"line": "cobalt", "ink": "navy", "sheet": "navy"}}')
        bk.use_themes(self.root)
        plate = dict(name="x", label="A", message="B", style="blueprint-flat")
        ours = bk.files_for(dict(plate, print="navyprint"))
        theirs = bk.files_for(dict(plate, print="blueprint"))
        self.assertEqual(ours.keys(), theirs.keys())
        import re

        def same_ids(svg: str) -> str:
            # Only the ids differ, since their seed carries the print's name.
            return svg.replace(re.search(r'id="p([0-9a-f]{6})"', svg).group(1), "uid")

        for path in ours:
            self.assertEqual(same_ids(ours[path]), same_ids(theirs[path]), path)

    def test_every_fault_in_a_themes_file_is_named(self):
        self.write('{"blackprint": {"line": "#000000", "ink": "#000000", "sheet": "#000000"},'
                   ' "Gold Print": {"line": "iris", "ink": "indigo", "sheet": "indigo"},'
                   ' "tinprint": {"line": "tin", "ink": "black", "sheet": "black"},'
                   ' "irisprint": {"line": "iris", "ink": "indigo"},'
                   ' "oddprint": {"line": "iris", "ink": "indigo", "sheet": "indigo", "shade": "black"},'
                   ' "rainbowprint": {"line": "iris", "ink": "indigo", "sheet": "indigo"}}')
        with self.assertRaises(bk.BadgeError) as err:
            bk.use_themes(self.root)
        for fault in ("blackprint: the kits already draw", "'Gold Print'", "'tin' is neither", "no 'sheet'",
                      "'shade' is not", "rainbowprint: the kits already draw"):
            self.assertIn(fault, str(err.exception))
        self.write("[]")
        with self.assertRaisesRegex(bk.BadgeError, "expected a map"):
            bk.use_themes(self.root)

    def test_themes_from_one_repository_never_reach_the_next(self):
        self.write(GOLD)
        bk.use_themes(self.root)
        self.assertIn("goldprint", bk.PRINTS)
        self.assertEqual(bk.use_themes(self.root / "elsewhere"), ())
        self.assertEqual(list(bk.PRINTS), list(bk.BUILTIN))


class Blueprint(unittest.TestCase):
    """Every style has a plate twin, drawn in a print, in two files."""

    def test_every_style_has_a_twin_with_its_geometry(self):
        # A twin keeps the base style's box, so swapping one for the other
        # never moves a row. A new style without a twin fails here.
        for key, g in bk.STYLES.items():
            twin = bk.BLUEPRINT_STYLES[bk.BLUEPRINT + key]
            for field in ("h", "pad", "icon", "gap", "rx", "sheen", "caps"):
                self.assertEqual(twin[field], g[field], f"{key}.{field}")
        self.assertEqual(len(bk.BLUEPRINT_STYLES), len(bk.STYLES))

    def test_a_plate_is_the_height_of_its_base_style(self):
        import re
        for key, g in bk.STYLES.items():
            svg = bk.render_blueprint("Build", "Passing", "check", bk.BLUEPRINT + key)
            self.assertIn(f'height="{g["h"]:g}"', re.search(r"<svg[^>]*>", svg).group(0), key)

    def test_every_colour_is_a_palette_token(self):
        import re
        tokens = {v.upper() for v in bk.PALETTE.values()}
        svgs = [bk.render_blueprint("A", "B", "pulse", s, t, d)
                for s in bk.BLUEPRINT_STYLES for t in bk.PRINTS for d in (False, True)]
        svgs += [bk.render_live("A", "B", "pulse", s, st)
                 for s in bk.BLUEPRINT_STYLES for st in bk.STATE_PRINT]
        for svg in svgs:
            for hexc in re.findall(r"#[0-9A-Fa-f]{6}\b", svg):
                self.assertIn(hexc.upper(), tokens)

    def test_every_print_and_state_print_is_drawn_in_tokens(self):
        for tone, p in bk.PRINTS.items():
            for role in ("line", "ink", "sheet"):
                self.assertIn(p[role], bk.PALETTE, f"{tone}.{role}")
            self.assertIn(p.get("night", "white"), ("white", "black"), tone)
        self.assertEqual(set(bk.STATE_PRINT), bk.HEALTH_COLORS | bk.HEALTH_NEUTRAL)
        for state, tone in bk.STATE_PRINT.items():
            self.assertIn(tone, bk.PRINTS, state)

    def test_yellow_is_not_drawn_in_the_gold_family(self):
        # A mustard block next to the gold sheet reads as one colour.
        svg = bk.render_live("Coverage", "78%", None, state="yellow")
        self.assertIn(bk.PALETTE["tangerine"], svg)
        self.assertNotIn(bk.PALETTE["mustard"], svg)

    def test_a_live_plate_accepts_the_state_as_a_hex(self):
        self.assertEqual(bk.render_live("A", "B", state="green"),
                         bk.render_live("A", "B", state=bk.PALETTE["green"].lower()))

    def test_reserve_holds_the_width_and_the_label_does_not_move(self):
        import re
        width = lambda svg: int(re.search(r'width="(\d+)"', svg).group(1))
        values = ("Passing", "Failing", "Pending")
        widths = {width(bk.render_live("Build", v, "check", state="green", reserve=values))
                  for v in values}
        self.assertEqual(len(widths), 1)
        self.assertGreaterEqual(widths.pop(),
                                width(bk.render_live("Build", "Passing", "check", state="green")))

    def test_the_lettering_is_paths_never_text(self):
        svg = bk.render_blueprint("Build Status", "Passing", "check")
        self.assertNotIn("<text", svg)
        self.assertIn('aria-label="Build Status: Passing"', svg)
        self.assertIn("<title>Build Status: Passing</title>", svg)

    def test_two_plates_can_share_a_page(self):
        # Every id carries the plate's own suffix, so inlining two plates
        # never lets one borrow the other's grid, sheen or glyphs.
        import re
        a = bk.render_blueprint("Build", "Passing", None, "blueprint-flat")
        b = bk.render_blueprint("Build", "Passing", None, "blueprint-flat", "redprint")
        ids = lambda svg: set(re.findall(r'\bid="([^"]+)"', svg))
        self.assertFalse(ids(a) & ids(b))

    def test_validation_refuses_what_a_plate_cannot_honour(self):
        base = dict(name="x", label="A", message="B", style="blueprint-flat")
        for bad, why in (
                (dict(base, message_color="teal"), "message_color on a static plate"),
                (dict(base, print="goldprint"), "an unknown print"),
                (dict(base, label_color="navy"), "a label neither black nor gold"),
                (dict(base, label_color="gold", message_color="green", print="redprint"),
                 "a print on a live plate"),
                (dict(base, label_color="gold", message_color="teal"), "a non-health state"),
                (dict(base, message="漢"), "a character the lettering lacks"),
                (dict(base, reserve="漢"), "a reserved value the lettering lacks"),
                (dict(name="x", label="A", message="B", print="redprint"), "print on a classic style"),
                (dict(name="x", label="A", message="B", reserve="C"), "reserve on a classic style"),
                (dict(base, style="blueprint-3d"), "an unknown plate style")):
            self.assertTrue(bk.validate([bad]), why)
        for good in (base, dict(base, print="yellowprint"),
                     dict(base, label_color="gold", message_color="slate", reserve="C, D")):
            self.assertEqual(bk.validate([good]), [], good)

    def test_a_rainbowprint_plate_follows_the_banners(self):
        base = dict(name="x", label="A", message="B", style="blueprint-flat")
        self.assertEqual(bk.validate([dict(base, print="rainbowprint")]), [])
        self.assertIn("or rainbowprint", bk.validate([dict(base, print="goldprint")])[0])
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(bk.rainbow_shade(root), "redprint", "without banners, the first colour")
            (root / ".github").mkdir()
            lock = root / ".github" / "banners.lock.json"
            for text, colour in (('{"rainbow": "tealprint"}', "tealprint"), ('{"rainbow": "goldprint"}', "redprint"),
                                 ('{"last": null}', "redprint"), ("not json", "redprint"), ("[]", "redprint")):
                lock.write_text(text)
                self.assertEqual(bk.rainbow_shade(root), colour, text)
        self.assertEqual(bk.files_for(dict(base, print="rainbowprint"), "tealprint"),
                         bk.files_for(dict(base, print="tealprint")))
        self.assertEqual(bk.files_for(dict(base, print="rainbowprint")), bk.files_for(dict(base, print="redprint")))

    def test_a_theme_draws_every_static_plate_in_its_print_and_leaves_the_rest(self):
        base = dict(name="x", label="A", message="B", style="blueprint-flat")
        live = dict(base, name="y", label_color="gold", message_color="green")
        classic = dict(name="z", label="A", message="B", label_color="black", message_color="green")
        self.assertEqual(bk.files_for(dict(base, print="redprint"), theme="blackprint"),
                         bk.files_for(dict(base, print="blackprint")), "the theme wins over the plate's print")
        self.assertEqual(bk.files_for(base, theme="tealprint"), bk.files_for(dict(base, print="tealprint")),
                         "and over the default print")
        self.assertEqual(bk.files_for(base, "tealprint", theme="rainbowprint"),
                         bk.files_for(dict(base, print="tealprint")), "a rainbowprint theme follows the banners")
        self.assertEqual(bk.files_for(live, theme="blackprint"), bk.files_for(live), "a live plate keeps its state")
        self.assertEqual(bk.files_for(classic, theme="blackprint"), bk.files_for(classic), "a classic badge its colours")

    def test_a_night_file_cannot_collide_with_another_badge(self):
        errors = bk.validate([dict(name="x", label="A", message="B", style="blueprint-flat"),
                              dict(name="x-dark", label="A", message="B")])
        self.assertTrue(any("static/x-dark.svg" in e for e in errors), errors)

    def test_reserve_reads_the_same_from_either_parser(self):
        self.assertEqual(bk._reserve({"reserve": "[Failing, Pending]"}), ("Failing", "Pending"))
        self.assertEqual(bk._reserve({"reserve": "Failing, 'Pending'"}), ("Failing", "Pending"))
        self.assertEqual(bk._reserve({}), ())

    def test_randomize_leaves_a_plate_alone(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "badges.yml"
            p.write_text(PLATES, encoding="utf-8")
            self.assertEqual(bk.randomize_static(p, "2026-W39"), [])
            self.assertEqual(p.read_text(encoding="utf-8"), PLATES)

    def test_the_gallery_draws_every_plate_style_print_and_state(self):
        names = bk.gallery_filenames()
        for key in bk.BLUEPRINT_STYLES:
            for suffix in ("", "-dark", "-live"):
                self.assertIn(f"gallery-{key}{suffix}.svg", names)
        for tone in bk.PRINTS:
            self.assertIn(f"gallery-print-{tone}.svg", names)
            self.assertIn(f"gallery-print-{tone}-dark.svg", names)
        for state in bk.STATE_PRINT:
            self.assertIn(f"gallery-state-{state}.svg", names)

    def test_the_readme_states_the_plate_count(self):
        counts = bk.combination_count()
        self.assertEqual(counts["blueprint"], counts["plates"] + counts["live_plates"])
        readme = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
        for key in ("blueprint", "plates", "live_plates"):
            self.assertTrue(f"{counts[key]:,}" in readme,
                            f"README does not state the counted {key} ({counts[key]:,})")


class BlueprintCli(unittest.TestCase):
    """A static plate is two files; a live one is one; both are pruned."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".github").mkdir()
        self.data = self.root / ".github" / "badges.yml"
        self.data.write_text(PLATES, encoding="utf-8")
        self.out = self.root / "assets" / "badges"

    def tearDown(self):
        self.tmp.cleanup()

    def render(self, *extra: str) -> tuple[int, str]:
        return run(["--root", str(self.root), *extra])

    def test_a_static_plate_writes_a_day_and_a_night_file(self):
        self.assertEqual(self.render()[0], 0)
        self.assertTrue((self.out / "static" / "status.svg").is_file())
        self.assertTrue((self.out / "static" / "status-dark.svg").is_file())
        self.assertTrue((self.out / "dynamic" / "build.svg").is_file())
        self.assertFalse((self.out / "dynamic" / "build-dark.svg").exists(),
                         "a live plate is one file for both themes")
        self.assertNotEqual((self.out / "static" / "status.svg").read_text(encoding="utf-8"),
                            (self.out / "static" / "status-dark.svg").read_text(encoding="utf-8"))

    def test_markdown_embeds_a_static_plate_as_a_picture(self):
        code, out = self.render("--markdown")
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(
            lines[0],
            '<a href="./"><picture><source media="(prefers-color-scheme: dark)" '
            'srcset="assets/badges/static/status-dark.svg"><img alt="Status: Active" '
            'src="assets/badges/static/status.svg"></picture></a>')
        self.assertEqual(lines[1], "![Build: Passing](assets/badges/dynamic/build.svg)")

    def test_a_theme_redraws_the_static_plates_and_check_holds_it_to_them(self):
        self.render()
        build = (self.out / "dynamic" / "build.svg").read_text(encoding="utf-8")
        self.assertEqual(self.render("--theme", "blackprint")[0], 0)
        self.assertEqual((self.out / "static" / "status.svg").read_text(encoding="utf-8"),
                         bk.files_for(dict(name="status", label="Status", message="Active", icon="pulse",
                                           style="blueprint-flat", print="blackprint"))["static/status.svg"])
        self.assertEqual((self.out / "dynamic" / "build.svg").read_text(encoding="utf-8"), build)
        self.assertEqual(self.render("--check", "--theme", "blackprint")[0], 0)
        self.assertEqual(self.render("--check")[0], 1, "without the theme the plate reads as stale")

    def test_an_unknown_theme_is_refused_with_the_prints_named(self):
        code, out = self.render("--theme", "goldprint")
        self.assertEqual(code, 1)
        self.assertIn("blackprint", out)
        self.assertFalse(self.out.exists(), "nothing is drawn")

    def themes(self, text: str) -> None:
        (self.root / ".github" / "themes.json").write_text(text, encoding="utf-8")
        self.addCleanup(bk.use_themes, None)  # the next test starts from the kit's own prints

    def test_a_repository_theme_draws_the_static_plates_in_its_own_colours(self):
        self.themes(GOLD)
        self.data.write_text(PLATES.replace("print: greenprint", "print: goldprint"), encoding="utf-8")
        code, out = self.render()
        self.assertEqual(code, 0, out)
        self.assertIn("#B8860B", (self.out / "static" / "status.svg").read_text(encoding="utf-8"))
        self.assertIn("#7A5B00", (self.out / "static" / "status-dark.svg").read_text(encoding="utf-8"))
        self.assertEqual(self.render("--check")[0], 0, "and check draws it the same way")

    def test_the_theme_option_can_name_a_repository_theme(self):
        self.themes(GOLD)
        self.render()
        build = (self.out / "dynamic" / "build.svg").read_text(encoding="utf-8")
        code, out = self.render("--theme", "goldprint")
        self.assertEqual(code, 0, out)
        self.assertIn("#5C4400", (self.out / "static" / "status.svg").read_text(encoding="utf-8"))
        self.assertEqual((self.out / "dynamic" / "build.svg").read_text(encoding="utf-8"), build,
                         "a live plate keeps its state's colours")

    def test_a_theme_nobody_defined_points_at_the_themes_file(self):
        code, out = self.render("--theme", "goldprint")
        self.assertEqual(code, 1)
        self.assertIn(".github/themes.json", out)
        self.data.write_text(PLATES.replace("print: greenprint", "print: goldprint"), encoding="utf-8")
        code, out = self.render()
        self.assertEqual(code, 1)
        self.assertIn(".github/themes.json", out)

    def test_a_broken_themes_file_fails_the_run_with_every_fault_named(self):
        self.themes('{"blackprint": {"line": "#000000", "ink": "#000000", "sheet": "#000000"},'
                    ' "tinprint": {"line": "tin", "ink": "black", "sheet": "black"}}')
        code, out = self.render()
        self.assertEqual(code, 1)
        self.assertIn("blackprint: the kits already draw", out)
        self.assertIn("'tin' is neither", out)
        self.assertFalse(self.out.exists(), "nothing is drawn")
        self.themes("{not json")
        self.assertIn("JSON", self.render()[1])

    def test_check_without_a_data_file_skips_before_it_reads_the_themes(self):
        self.data.unlink()
        self.themes("{not json")
        self.assertEqual(self.render("--check")[0], 0, "a repository that does not use badges is not failed")

    def test_check_catches_a_stale_night_file(self):
        self.render()
        self.assertEqual(self.render("--check")[0], 0)
        (self.out / "static" / "status-dark.svg").write_text("<svg/>", encoding="utf-8")
        code, out = self.render("--check")
        self.assertEqual(code, 1)
        self.assertIn("static/status-dark", out)

    def test_the_night_file_is_pruned_when_the_plate_goes_classic(self):
        self.render()
        self.data.write_text(PLATES.replace("    style: blueprint-flat\n    print: greenprint\n", ""),
                             encoding="utf-8")
        self.assertEqual(self.render()[0], 0)
        self.assertTrue((self.out / "static" / "status.svg").is_file())
        self.assertFalse((self.out / "static" / "status-dark.svg").exists())

    def test_set_updates_a_live_plate(self):
        code, _ = self.render("--set", "build=Failing:red")
        self.assertEqual(code, 0)
        svg = (self.out / "dynamic" / "build.svg").read_text(encoding="utf-8")
        self.assertIn('aria-label="Build: Failing"', svg)
        self.assertIn(bk.PALETTE["cherry"], svg, "red is drawn in the redprint")

    def test_the_codemod_counts_a_night_file_as_its_own(self):
        lb = load("localize_badges_plates", "localize-badges.py")
        lb.configure(self.root, self.data, self.out)
        own = lb.own_badge_files()
        self.assertIn("status-dark.svg", own)
        self.assertIn("build.svg", own)
