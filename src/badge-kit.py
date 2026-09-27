#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Tanner Golden
# SPDX-FileCopyrightText: 2018 Metabolize LLC (anafanafo font-metrics data)
# SPDX-License-Identifier: MIT
"""Self-hosted badge kit - renders committed SVG badges, no third party.

A repository's badges are drawn here instead of hotlinked to a badge
service, so it never depends on an external endpoint at render time and
can never be rate-limited. One generator turns a small data file
(`.github/badges.yml`) into committed SVGs under `assets/badges/`, in the
repository's own styles with an in-house icon set.

The kit is a standalone repository, consumed as a composite action:
`uses: tannergolden/badges@v1` in a consumer's workflow runs this file
against that consumer's checkout, so every repository pinned to the major
tag inherits new icons, styles, and fixes the moment it moves. The DATA
file is the consumer's own - `.github/badges.yml` in their repository lists
the badges they want and is never overwritten.

Design contract (matches the Document Styling & Formatting standard in
tannergolden/standards, docs/technical/interface/Document-Styling-&-Formatting.md):
  - Six interchangeable styles, grouped by the job. Headline: `for-the-badge`
    (the default; bold uppercase, 28px). Standard: `flat` (20px, rounded,
    subtle gradient), `flat-square` (square corners, no gradient), `plastic`
    (18px, bevelled) and `pill` (20px, fully round). Dense: `compact` (16px).
    Documentation headers keep `for-the-badge` per the standard.
  - Static badges use a black label; dynamic-health badges use the metallic
    gold label. Message color carries the semantic meaning.
  - Badges are solid chips, so they render identically in light and dark
    themes.
  - Every style has a blueprint twin (`blueprint-flat` and so on), drawn like
    tannergolden/banners: lettered in outlined Barlow Condensed, a static
    plate in one of eleven prints as a day and a night file, a live plate
    (gold label) in its state's print as one.
  - Text is measured with real Verdana metrics and pinned with SVG
    `textLength`, so a badge renders at the same width on every platform.

Usage:
  python3 src/badge-kit.py                   # render .github/badges.yml     (make render)
  python3 src/badge-kit.py --check           # committed SVGs are current    (make check)
  python3 src/badge-kit.py --set build=Passing:green   # update a value, re-render
  python3 src/badge-kit.py --gallery         # draw every icon, token, style (make gallery)
  python3 src/badge-kit.py --icons           # list the icon registry        (make icons)
  python3 src/badge-kit.py --palette         # list the palette tokens       (make palette)
  python3 src/badge-kit.py --self-test       # renderer + parser invariants  (make self-test)
`make badges` localizes any hotlinks, renders, and refreshes the gallery.
The gate is `make check`: self-test, committed-SVG drift, gallery drift, and
no shields.io hotlink left. `make test` runs that plus the unit tests under
tests/unit/.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from html import escape
from pathlib import Path

# Bumped whenever rendered output changes for the same input. Every SVG is
# stamped with it; --check hard-fails only same-version drift (stale data),
# and treats a version difference as "regenerate on the next render" so an
# engine sync that updates this renderer can never wedge a downstream CI.
KIT_VERSION = "2"
# sha256 of one canonical render. The self-test fails when rendered output
# changes while this constant (and therefore KIT_VERSION) was not updated -
# the mechanical discipline that keeps --check's version tolerance honest.
GOLDEN_SHA = "88c8a1466bc92d915ab395eb6c48e55548bd2ce94d8e71d1ae0f773d56a30e2f"
# The same discipline for a blueprint plate: its day, night and live files,
# hashed together, so neither drawing can change behind the version's back.
GOLDEN_BLUEPRINT_SHA = "4541b980da39aefd4f67290c2d9cb003dccf97158a0a41f5756f88e399affa80"

# --------------------------------------------------------------------------- #
# Palette - named tokens keep the data file readable and on-spec. Values map
# to the doc-style color roles; a raw #RRGGBB hex also works anywhere a token
# does, so the space of colors (and therefore badges) stays unbounded.
#
# One designed family. The role anchors below are brand-fixed; the extended
# spectrum and the earth/neutral tones are tuned to a consistent saturation
# and lightness band (chromatics land near S60 L50) so any two tokens sit
# together without clashing - a full rainbow plus the popular colors, all
# synergized. HEALTH is the reserved traffic-light subset: a dynamic-health
# badge (gold label) may only paint its message with one of these to signal
# status (red/yellow/green), plus slate for an explicit "no status yet".
# --------------------------------------------------------------------------- #
PALETTE = {
    # --- Role anchors (brand-fixed; the doc-style color roles) --------------
    "black": "#000000",   # static label (doc-style: labelColor 000000)
    "gold": "#C0A062",    # dynamic-health label (doc-style: C0A062)
    "green": "#2EA043",   # success / active / healthy
    "pink": "#FE5196",    # roles / community
    "purple": "#9C27B0",  # context / technology
    "yellow": "#F1E05A",  # license / legal / degraded
    "red": "#D73A49",     # security / critical / failing
    "blue": "#3366FF",    # navigation / info
    "violet": "#8B6CFF",  # docs-site accent
    "olive": "#8A8B2C",   # muted score
    "slate": "#57606A",   # neutral / unknown
    "teal": "#1F9E8F",    # metrics
    "orange": "#E36209",  # warning
    "white": "#FFFFFF",
    # --- Extended spectrum (rainbow order; harmonized S/L) ------------------
    "crimson": "#CB2A4A",  # deep red
    "ruby": "#AB2B5A",     # wine red
    "rose": "#E7557C",     # soft red-pink
    "magenta": "#CF3095",  # hot pink-purple
    "fuchsia": "#E147C2",  # bright magenta
    "plum": "#9D47AE",     # muted purple
    "indigo": "#534DCB",   # blue-violet
    "azure": "#3687E2",    # strong blue
    "sky": "#3E9CE0",      # light blue
    "cyan": "#2FADC6",     # blue-green
    "aqua": "#36C9C5",     # bright teal
    "mint": "#4DCBA5",     # light green-teal
    "emerald": "#2BB675",  # rich green
    "lime": "#6FBE37",     # yellow-green
    "amber": "#DFAD3A",    # deep yellow
    "coral": "#EC7051",    # red-orange
    # --- Earth & neutral tones ---------------------------------------------
    "peach": "#EFA980",    # warm light orange
    "sand": "#D0BD8B",     # pale tan
    "tan": "#CAA472",      # warm neutral
    "brown": "#8D5A35",    # earthy brown
    "maroon": "#7E303D",   # deep brownish red
    "navy": "#253D7E",     # deep blue
    "forest": "#22773E",   # deep green
    "lavender": "#AC94E6",  # pale violet
    "steel": "#5B758F",    # blue-grey
    "gray": "#7A8390",     # neutral grey
    # --- Second spectrum: one token per icon, same S/L family --------------
    # Added so the palette and the icon registry are the same size, and so
    # every family has a light, a mid and a deep option rather than one pick.
    # Each was checked against every other token and clears the palette's own
    # minimum spacing (gold vs tan), so no two read as the same color.
    "cherry": "#C32837",    # vivid true red
    "brick": "#A6503A",     # muted red-brown
    "salmon": "#DC796A",    # light warm pink-orange
    "tangerine": "#DD732C", # vivid orange
    "apricot": "#E0A367",   # light orange
    "honey": "#CE8B27",     # deep golden orange
    "mustard": "#B1932F",   # dark yellow
    "ivory": "#ECE3CB",     # warm off-white
    "moss": "#6E883A",      # dark yellow-green
    "sage": "#7AA465",      # muted grey-green
    "jade": "#389F79",      # green with blue in it
    "turquoise": "#2FB1A9", # bright blue-green
    "ocean": "#277C9B",     # deep blue-cyan
    "cobalt": "#2F66C6",    # strong blue
    "denim": "#4977AB",     # muted mid blue
    "iris": "#6C54C9",      # blue-violet
    "amethyst": "#884CBD",  # mid purple
    "mauve": "#A564AF",     # muted purple
    "orchid": "#CE64BC",    # light purple-pink
    "clay": "#A0644B",      # earthy red-brown
    "taupe": "#8E7967",     # warm grey-brown
    "stone": "#A19687",     # pale warm grey
    "ash": "#ABB3BA",       # light cool grey
    "charcoal": "#3A414A",  # near-black neutral
}
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

# The traffic-light subset a dynamic-health badge may use to represent a
# STATUS with color (plus slate as the reserved "no status yet" neutral).
# Enforced in validate() and documented in Document-Styling-&-Formatting.md.
HEALTH_COLORS = {"green", "yellow", "red"}
HEALTH_NEUTRAL = {"slate"}

# The pool a randomized STATIC badge draws its message color from (see
# randomize_static): the whole designed palette EXCEPT the reserved tokens -
# the traffic-light triad (a static badge must never resemble a status), the
# black label color, the gold dynamic-health label, the slate neutral, and
# white (invisible on GitHub's canvas). Sorted for deterministic indexing.
_RANDOM_RESERVED = (
    HEALTH_COLORS
    | HEALTH_NEUTRAL
    | {"black", "gold", "white"}
    # Slot colors the docs law fixes for header identity badges: pink is
    # the Role/Identification slot (FE5196) and purple the Context slot
    # (9C27B0). Rotation must neither repaint a slot badge away from its
    # mandated color nor paint a decorative badge INTO one - either way
    # check-docs-style.py's badge-slot rules would fail the tree.
    | {"pink", "purple"}
)
STATIC_RANDOM_POOL = sorted(t for t in PALETTE if t not in _RANDOM_RESERVED)

# --------------------------------------------------------------------------- #
# In-house icon set - line glyphs on a 24x24 grid, drawn here so the kit never
# pulls a logo from a third-party icon CDN. Each glyph is stroked in the
# label's ink color at render time, so it reads on any background. Add a glyph
# by dropping a new 24x24 stroke path into this registry.
# --------------------------------------------------------------------------- #
ICONS = {
    "pulse": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "shield": '<path d="M12 2l8 3v6c0 5-3.5 8.6-8 10-4.5-1.4-8-5-8-10V5z"/>',
    "book": '<path d="M5 4h11a1 1 0 0 1 1 1v15H6a1 1 0 0 1-1-1z"/><path d="M17 5h2v15h-2"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    "scale": '<path d="M12 3v18M7 21h10M12 6l-7 2 3 6a3 3 0 0 1-6 0l3-6M12 6l7 2-3 6a3 3 0 0 0 6 0l-3-6"/>',
    "commit": '<circle cx="12" cy="12" r="3.2"/><path d="M3 12h5.8M15.2 12H21"/>',
    "branch": '<circle cx="6" cy="6" r="2.4"/><circle cx="6" cy="18" r="2.4"/><circle cx="18" cy="7" r="2.4"/><path d="M6 8.4v7.2M6 12a6 6 0 0 0 6-6h3.6"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
    "cross": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l1.8 1.8M17.2 17.2L19 19M19 5l-1.8 1.8M6.8 17.2L5 19"/>',
    "star": '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 17l-5.2 2.6 1-5.8L3.5 9.7l5.9-.9z"/>',
    "grid": '<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/>',
    "arrow": '<path d="M4 12h15M13 6l6 6-6 6"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.2-4.2"/>',
    "heart": '<path d="M12 20s-7-4.5-9.5-9C1 8 3 4 6.5 4 9 4 12 7.5 12 7.5S15 4 17.5 4C21 4 23 8 21.5 11c-2.5 4.5-9.5 9-9.5 9z"/>',
    "package": '<path d="M21 8l-9-5-9 5v8l9 5 9-5z"/><path d="M3 8l9 5 9-5M12 13v10"/>',
    "tag": '<path d="M11 3H4v7l10 10 7-7z"/><circle cx="7.5" cy="6.5" r="1.3"/>',
    "download": '<path d="M12 3v12M7 11l5 5 5-5M4 20h16"/>',
    "upload": '<path d="M12 21V9M7 13l5-5 5 5M4 4h16"/>',
    "cloud": '<path d="M7 18a4 4 0 0 1-.5-7.97A5.5 5.5 0 0 1 17 9.5a3.5 3.5 0 0 1 .5 6.98z"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/>',
    "code": '<path d="M8 6l-5 6 5 6M16 6l5 6-5 6"/>',
    "bug": '<rect x="8" y="8" width="8" height="11" rx="4"/><path d="M8 12H3M16 12h5M8 16H4M16 16h4M9 8L7 5M15 8l2-3M12 8V5"/>',
    "flask": '<path d="M9 3h6M10 3v6l-5.2 9.2A2 2 0 0 0 6.5 21h11a2 2 0 0 0 1.7-2.8L14 9V3"/><path d="M7.5 15h9"/>',
    "rocket": '<path d="M5 15c-1.5 1.5-2 6-2 6s4.5-.5 6-2M9 15a10 10 0 0 1 9-12s1 .1 1.9.2c.1.9.1 1.9.1 1.9A10 10 0 0 1 9 15z"/><circle cx="14.5" cy="8.5" r="1.5"/>',
    "flame": '<path d="M12 3s5 4 5 9a5 5 0 0 1-10 0c0-2 1-3.2 1-3.2s.2 1.7 1.6 1.7C13 10.5 12 3 12 3z"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="2.5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/>',
    "chart": '<path d="M4 4v16h16M8 16v-4M12 16V8M16 16v-7"/>',
    "database": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.66 3.58 3 8 3s8-1.34 8-3V6M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3M14 9l2 2"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z"/>',
    "users": '<circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0M16 5.2a3.2 3.2 0 0 1 0 5.6M18 20a6 6 0 0 0-4-5.6"/>',
    "chat": '<path d="M4 5h16v11H9l-4 4V5z"/><path d="M8 10h8M8 13h5"/>',
    "flag": '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
    "trophy": '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a2 2 0 0 0 2 4M16 6h3a2 2 0 0 1-2 4M9 21h6M12 15v3M10 15h4"/>',
    "sparkle": '<path d="M12 3l2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2z"/>',
    "medal": '<circle cx="12" cy="10" r="5"/><path d="M9 14l-2 7 5-3 5 3-2-7"/>',
    "chip": '<rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 2v3M14 2v3M10 19v3M14 19v3M2 10h3M2 14h3M19 10h3M19 14h3"/>',
    "link": '<path d="M9 15l6-6M8.5 11l-2 2a3 3 0 0 0 4 4l2-2M15.5 13l2-2a3 3 0 0 0-4-4l-2 2"/>',
    "folder": '<path d="M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>',
    "sync": '<path d="M4 12a8 8 0 0 1 13.9-5.4L20 9M20 12a8 8 0 0 1-13.9 5.4L4 15M17 4v5h-5M7 20v-5h5"/>',
    "alert": '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "play": '<path d="M7 4l13 8-13 8z"/>',
    "home": '<path d="M4 11l8-7 8 7M6 9.5V20h12V9.5M10 20v-6h4v6"/>',
    "server": '<rect x="3" y="4" width="18" height="7" rx="1.5"/><rect x="3" y="13" width="18" height="7" rx="1.5"/><path d="M7 7.5h.01M7 16.5h.01"/>',
    "bell": '<path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6"/><path d="M10 19a2.2 2.2 0 0 0 4 0"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="M3 7l9 6 9-6"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2"/>',
    "compass": '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/><path d="M10 11v6M14 11v6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "question": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.8 2.1c-.8.5-1.3 1-1.3 1.9v.5"/><path d="M12 17h.01"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/>',
    "moon": '<path d="M20 14.5A8 8 0 1 1 9.5 4 6.5 6.5 0 0 0 20 14.5z"/>',
    "infinity": '<path d="M7 9c-4 0-4 6 0 6 4 0 6-6 10-6 4 0 4 6 0 6-4 0-6-6-10-6z"/>',
}

FONT = "Verdana,'DejaVu Sans',Geneva,sans-serif"

# --------------------------------------------------------------------------- #
# Character advance widths, measured from the real font so a badge is sized
# the way shields.io sizes its own (no more guessed average width: 'W' is
# 12.4px, 'I' is 6.0px). Ranges are (loCodepoint, hiCodepoint, px). Derived
# from the MIT-licensed anafanafo dataset (Copyright (c) 2018 Metabolize LLC,
# the measurement tables shields.io itself uses): Verdana bold 10px scaled
# linearly to 11px, and Verdana normal 11px as-is. Non-ASCII falls back to a
# generous default so a badge can pad, never overflow. `textLength` on every
# <text> pins the rendered run to these widths on every platform, so a
# viewer without Verdana (Linux/DejaVu) sees the same badge geometry.
# --------------------------------------------------------------------------- #
_W_BOLD11 = (
    (32, 32, 3.762), (33, 33, 4.422), (34, 34, 6.457), (35, 35, 9.537),
    (36, 36, 7.821), (37, 37, 13.992), (38, 38, 9.482), (39, 39, 3.652),
    (40, 41, 5.973), (42, 42, 7.821), (43, 43, 9.537), (44, 44, 3.971),
    (45, 45, 5.28), (46, 46, 3.971), (47, 47, 7.579), (48, 57, 7.821),
    (58, 59, 4.422), (60, 62, 9.537), (63, 63, 6.787), (64, 64, 10.604),
    (65, 65, 8.536), (66, 66, 8.382), (67, 67, 7.964), (68, 68, 9.13),
    (69, 69, 7.513), (70, 70, 7.15), (71, 71, 8.921), (72, 72, 9.207),
    (73, 73, 6.006), (74, 74, 6.105), (75, 75, 8.481), (76, 76, 7.007),
    (77, 77, 10.428), (78, 78, 9.317), (79, 79, 9.35), (80, 80, 8.063),
    (81, 81, 9.35), (82, 82, 8.602), (83, 83, 7.81), (84, 84, 7.502),
    (85, 85, 8.932), (86, 86, 8.404), (87, 87, 12.408), (88, 88, 8.404),
    (89, 89, 8.107), (90, 90, 7.612), (91, 91, 5.973), (92, 92, 7.579),
    (93, 93, 5.973), (94, 94, 9.537), (95, 96, 7.821), (97, 97, 7.348),
    (98, 98, 7.689), (99, 99, 6.468), (100, 100, 7.689), (101, 101, 7.304),
    (102, 102, 4.642), (103, 103, 7.689), (104, 104, 7.832), (105, 105, 3.762),
    (106, 106, 4.433), (107, 107, 7.381), (108, 108, 3.762), (109, 109, 11.638),
    (110, 110, 7.832), (111, 111, 7.557), (112, 113, 7.689), (114, 114, 5.467),
    (115, 115, 6.523), (116, 116, 5.016), (117, 117, 7.832), (118, 118, 7.15),
    (119, 119, 10.769), (120, 120, 7.359), (121, 121, 7.161), (122, 122, 6.567),
    (123, 123, 7.821), (124, 124, 5.973), (125, 125, 7.821), (126, 126, 9.537),
)
_W_NORM11 = (
    (32, 32, 3.87), (33, 33, 4.33), (34, 34, 5.05), (35, 35, 9.0),
    (36, 36, 6.99), (37, 37, 11.84), (38, 38, 7.99), (39, 39, 2.95),
    (40, 41, 5.0), (42, 42, 6.99), (43, 43, 9.0), (44, 44, 4.0),
    (45, 45, 5.0), (46, 46, 4.0), (47, 47, 5.0), (48, 57, 6.99),
    (58, 59, 5.0), (60, 62, 9.0), (63, 63, 6.0), (64, 64, 11.0),
    (65, 65, 7.52), (66, 66, 7.54), (67, 67, 7.68), (68, 68, 8.48),
    (69, 69, 6.96), (70, 70, 6.32), (71, 71, 8.53), (72, 72, 8.27),
    (73, 73, 4.63), (74, 74, 5.0), (75, 75, 7.62), (76, 76, 6.12),
    (77, 77, 9.27), (78, 78, 8.23), (79, 79, 8.66), (80, 80, 6.63),
    (81, 81, 8.66), (82, 82, 7.65), (83, 83, 7.52), (84, 84, 6.78),
    (85, 85, 8.05), (86, 86, 7.52), (87, 87, 10.88), (88, 88, 7.54),
    (89, 89, 6.77), (90, 90, 7.54), (91, 93, 5.0), (94, 94, 9.0),
    (95, 96, 6.99), (97, 97, 6.61), (98, 98, 6.85), (99, 99, 5.73),
    (100, 100, 6.85), (101, 101, 6.55), (102, 102, 3.87), (103, 103, 6.85),
    (104, 104, 6.96), (105, 105, 3.02), (106, 106, 3.79), (107, 107, 6.51),
    (108, 108, 3.02), (109, 109, 10.7), (110, 110, 6.96), (111, 111, 6.68),
    (112, 113, 6.85), (114, 114, 4.69), (115, 115, 5.73), (116, 116, 4.33),
    (117, 117, 6.96), (118, 118, 6.51), (119, 119, 9.0), (120, 121, 6.51),
    (122, 122, 5.78), (123, 123, 6.98), (124, 124, 5.0), (125, 125, 6.98),
    (126, 126, 9.0),
)

# Style geometry. `ls` is inter-character letter-spacing; `caps` uppercases
# the text (the for-the-badge identity); `rx` is the corner radius, 0 for
# square; `sheen` picks the overlay gradient, None for a flat chip; `mscale`
# scales the 11px metric tables to this style's font size, since the tables
# are measured at 11px and advance widths are linear in size.
#
# rx and sheen were one `deco` flag until a rounded-but-flat style needed
# them apart. Every combination is now reachable, which is what the pill and
# compact styles are.
SHEENS = {
    # The classic flat wash: a barely-there light-to-dark overlay.
    "soft": ('<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
             '<stop offset="1" stop-opacity=".1"/>'),
    # The plastic bevel: a bright top edge falling to a dark bottom one.
    "deep": ('<stop offset="0" stop-color="#fff" stop-opacity=".7"/>'
             '<stop offset=".1" stop-color="#aaa" stop-opacity=".1"/>'
             '<stop offset=".9" stop-color="#000" stop-opacity=".3"/>'
             '<stop offset="1" stop-color="#000" stop-opacity=".5"/>'),
}

STYLES = {
    # --- Headline: bold uppercase, letter-spaced. Mastheads and doc headers.
    "for-the-badge": dict(h=28.0, pad=12.0, icon=15.0, gap=6.0, fs=11,
                          weight="700", ls=1.0, caps=True, y=18.5,
                          table=_W_BOLD11, fallback=11.0, mscale=1.0,
                          rx=0.0, sheen=None),
    # --- Standard: natural case, body rows. Square, rounded, bevelled, round.
    "flat": dict(h=20.0, pad=6.0, icon=14.0, gap=3.0, fs=11,
                 weight="400", ls=0.0, caps=False, y=14.0,
                 table=_W_NORM11, fallback=9.0, mscale=1.0,
                 rx=3.0, sheen="soft"),
    "flat-square": dict(h=20.0, pad=6.0, icon=14.0, gap=3.0, fs=11,
                        weight="400", ls=0.0, caps=False, y=14.0,
                        table=_W_NORM11, fallback=9.0, mscale=1.0,
                        rx=0.0, sheen=None),
    # The shape shields.io calls plastic. The codemod maps a plastic hotlink
    # onto this rather than flattening it, so a migration keeps its look.
    "plastic": dict(h=18.0, pad=6.0, icon=12.0, gap=3.0, fs=11,
                    weight="400", ls=0.0, caps=False, y=13.0,
                    table=_W_NORM11, fallback=9.0, mscale=1.0,
                    rx=4.0, sheen="deep"),
    # Wider padding, because a pill's round caps eat into the space the text
    # would otherwise sit in.
    "pill": dict(h=20.0, pad=10.0, icon=14.0, gap=4.0, fs=11,
                 weight="400", ls=0.0, caps=False, y=14.0,
                 table=_W_NORM11, fallback=9.0, mscale=1.0,
                 rx=10.0, sheen=None),
    # --- Dense: a table of twenty badges, or one inline in a sentence, where
    # the standard chip is taller than the line it sits on.
    "compact": dict(h=16.0, pad=5.0, icon=10.0, gap=3.0, fs=9,
                    weight="400", ls=0.0, caps=False, y=11.2,
                    table=_W_NORM11, fallback=9.0, mscale=9 / 11,
                    rx=2.0, sheen=None),
}

# Styles grouped by the job you are choosing them for, rather than by the
# order they were added. Same contract as ICON_GROUPS: drift-safe, with the
# gallery computing the leftovers, so a new style still reaches the page.
STYLE_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Headline", "Bold uppercase and letter-spaced. Mastheads, and the "
                 "document headers the styling standard expects.",
     ("for-the-badge",)),
    ("Standard", "Natural case, for a body row. The same chip square, "
                 "rounded, bevelled, or fully round.",
     ("flat", "flat-square", "plastic", "pill")),
    ("Dense", "Shorter than a line of text, for a table of many badges or "
              "one sitting inline in a sentence.",
     ("compact",)),
)

DEFAULT_STYLE = "for-the-badge"

# The kit renders badges for the repository it is RUN AGAINST, which is not
# the repository it lives in: as a composite action the checkout under test is
# GITHUB_WORKSPACE while this file sits in the action's own checkout. Resolve
# the target from the workspace (Actions), else the working directory (a local
# `make badges`), and never from __file__ - that would make every consumer
# render into the kit's own tree. --data/--out override both.
def workspace() -> Path:
    """The repository this run renders badges FOR."""
    ws = os.environ.get("GITHUB_WORKSPACE", "")
    if ws and Path(ws).is_dir():
        return Path(ws)
    return Path.cwd()


REPO_ROOT = workspace()
DEFAULT_DATA = REPO_ROOT / ".github" / "badges.yml"
OUT_DIR = REPO_ROOT / "assets" / "badges"
# The codemod is this file's SIBLING inside the kit, wherever the kit is
# checked out - it is not part of the consumer's tree.
KIT_DIR = Path(__file__).resolve().parent
_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_STAMP = re.compile(r"<!--badge-kit v(\w+)-->")


class BadgeError(ValueError):
    """A badge definition the generator refuses to render silently."""


def _lum(hexc: str) -> float:
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _ink(bg: str) -> str:
    """Black or white text, whichever reads on the segment color.

    The 0.6 luminance threshold is a deliberate brand choice: it keeps
    white ink on the metallic-gold label (the approved for-the-badge look,
    matching shields.io's own treatment of mid-tone colors) while flipping
    to dark ink on genuinely light segments like the license yellow.
    """
    return "#1f2328" if _lum(bg) > 0.6 else "#ffffff"


def _color(token: str, field: str) -> str:
    """Resolve a palette token or #RRGGBB hex; refuse anything else."""
    if token in PALETTE:
        return PALETTE[token]
    if _HEX_COLOR.match(token or ""):
        return token
    raise BadgeError(
        f"unknown color {token!r} for {field} - use a palette token "
        f"({', '.join(PALETTE)}) or #RRGGBB"
    )


def _text_width(s: str, table, fallback: float, ls: float) -> float:
    """Advance width of `s` from the font table, plus letter-spacing."""
    total = 0.0
    for ch in s:
        cp = ord(ch)
        for lo, hi, w in table:
            if lo <= cp <= hi:
                total += w
                break
        else:
            total += fallback
    if len(s) > 1:
        total += ls * (len(s) - 1)
    return total


def render(label: str, message: str, label_color: str = "black",
           message_color: str = "blue", icon: str | None = None,
           style: str = DEFAULT_STYLE) -> str:
    """Render one badge SVG. label/message are free text; colors are palette
    tokens or #RRGGBB; icon is a key in ICONS (or None); style is one of
    STYLES. Raises BadgeError on any input it cannot honor exactly."""
    if style not in STYLES:
        raise BadgeError(f"unknown style {style!r} - one of {', '.join(STYLES)}")
    if icon is not None and icon != "" and icon not in ICONS:
        raise BadgeError(
            f"unknown icon {icon!r} - list the registry with --icons"
        )
    g = STYLES[style]
    # The accessible name keeps the author's casing; only the DISPLAY text
    # is uppercased by the for-the-badge style.
    aria = f"{label}: {message}" if label and message else (label or message)
    if g["caps"]:
        label, message = label.upper(), message.upper()
    lc, mc = _color(label_color, "label_color"), _color(message_color, "message_color")
    li, mi = _ink(lc), _ink(mc)
    has = bool(icon) and icon in ICONS
    ms = g["mscale"]
    lt = _text_width(label, g["table"], g["fallback"], g["ls"] / ms) * ms
    mt = _text_width(message, g["table"], g["fallback"], g["ls"] / ms) * ms
    lw = g["pad"] + (g["icon"] + g["gap"] if has else 0) + lt + g["pad"]
    mw = g["pad"] + mt + g["pad"]
    w, h = lw + mw, g["h"]
    tx = g["pad"] + (g["icon"] + g["gap"] if has else 0)

    # Deterministic per-badge ids so many badges can be inlined in one page
    # without gradient/clip collisions (and --check stays byte-stable).
    uid = hashlib.md5(
        f"{label}|{message}|{lc}|{mc}|{icon}|{style}".encode()
    ).hexdigest()[:6]

    defs = clip_open = clip_close = sheen = ""
    grad = SHEENS.get(g["sheen"] or "", "")
    if g["rx"] or grad:
        inner = ""
        if grad:
            inner += (f'<linearGradient id="g{uid}" x2="0" y2="100%">'
                      f'{grad}</linearGradient>')
        if g["rx"]:
            inner += (f'<clipPath id="c{uid}"><rect width="{w:.1f}" '
                      f'height="{h:.0f}" rx="{g["rx"]:g}" fill="#fff"/></clipPath>')
        defs = f"<defs>{inner}</defs>"
        if g["rx"]:
            clip_open = f'<g clip-path="url(#c{uid})">'
            clip_close = "</g>"
        if grad:
            sheen = f'<rect width="{w:.1f}" height="{h:.0f}" fill="url(#g{uid})"/>'

    glyph = ""
    if has:
        glyph = (f'<g transform="translate({g["pad"]:.1f},{(h - g["icon"]) / 2:.1f}) '
                 f'scale({g["icon"] / 24:.4f})" fill="none" stroke="{li}" stroke-width="2.2" '
                 f'stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</g>')

    def cell(x: float, text: str, tw: float, ink: str) -> str:
        if not text:
            return ""
        shadow = ""
        if g["sheen"] and ink == "#ffffff":
            # The flat style's classic legibility shadow under white text.
            shadow = (f'<text x="{x:.1f}" y="{g["y"] + 1:.1f}" fill="#010101" '
                      f'fill-opacity=".3" text-anchor="middle" font-family="{FONT}" '
                      f'font-size="{g["fs"]}" font-weight="{g["weight"]}" '
                      f'textLength="{tw:.1f}">{escape(text)}</text>')
        spacing = f' letter-spacing="{g["ls"]:g}"' if g["ls"] else ""
        return (f'{shadow}<text x="{x:.1f}" y="{g["y"]:.1f}" fill="{ink}" '
                f'text-anchor="middle" font-family="{FONT}" font-size="{g["fs"]}" '
                f'font-weight="{g["weight"]}"{spacing} '
                f'textLength="{tw:.1f}">{escape(text)}</text>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'role="img" aria-label="{escape(aria)}">'
        f'<!--badge-kit v{KIT_VERSION}-->'
        f'<title>{escape(aria)}</title>{defs}{clip_open}'
        f'<rect width="{lw:.1f}" height="{h:.0f}" fill="{lc}"/>'
        f'<rect x="{lw:.1f}" width="{mw:.1f}" height="{h:.0f}" fill="{mc}"/>'
        f'{sheen}{clip_close}{glyph}'
        f'{cell(tx + lt / 2, label, lt, li)}'
        f'{cell(lw + mw / 2, message, mt, mi)}</svg>'
    )


# --------------------------------------------------------------------------- #
# Blueprint plates - every style again, drawn the way tannergolden/banners
# draws a header: the label lettered on drafting paper, the value on a solid
# block of the print, the whole plate framed in the print's line.
#
# A plate is lettered in outlined Barlow Condensed rather than set in a font,
# so no viewer's installed fonts can change a letter: every glyph is a path,
# embedded once per file and placed with <use>. The outlines are the ones
# banners draws with, in src/fonts/barlow-condensed.json (SIL OFL 1.1, see
# NOTICE), and a label or value with a character they lack is refused at
# validation rather than drawn with a hole in it.
#
# A STATIC plate is two files, `<name>.svg` for the day theme and
# `<name>-dark.svg` for the night one, because a print has a day and a night:
# its lines on white paper, and the sheet those lines are printed on. Embed
# the pair with <picture> (--markdown prints it). A LIVE plate - a gold
# label - is one file on a gold sheet with its value on a block of the state's
# print, since a state is the same state in either theme.
# --------------------------------------------------------------------------- #
BLUEPRINT = "blueprint-"

# A print is the colour a drawing is reproduced in: `line` for its linework
# and `ink` for its lettering on white paper by day, and by night the `sheet`
# those lines are printed on, lettered in `night` - white on the deep sheets,
# black on the two bright ones white could not be read on. The same eleven,
# in the same tokens, as tannergolden/banners, so a plate matches the banner
# above it.
PRINTS = {
    "redprint": dict(line="cherry", ink="maroon", sheet="cherry"),
    "orangeprint": dict(line="tangerine", ink="brick", sheet="tangerine", night="black"),
    "yellowprint": dict(line="mustard", ink="charcoal", sheet="mustard", night="black"),
    "greenprint": dict(line="forest", ink="forest", sheet="forest"),
    "tealprint": dict(line="teal", ink="ocean", sheet="ocean"),
    "blueprint": dict(line="cobalt", ink="navy", sheet="navy"),
    "indigoprint": dict(line="iris", ink="indigo", sheet="indigo"),
    "purpleprint": dict(line="plum", ink="amethyst", sheet="amethyst"),
    "pinkprint": dict(line="magenta", ink="ruby", sheet="ruby"),
    "brownprint": dict(line="brown", ink="brown", sheet="brown"),
    "blackprint": dict(line="charcoal", ink="black", sheet="charcoal"),
}
DEFAULT_PRINT = "blueprint"

# The rainbow, in the banners' order. A plate in `rainbowprint` is drawn in
# the colour the page's banners are in now: the banners kit remembers which
# colour of the spectrum its last update took in its lock, and a plate that
# follows it changes colour with the header above it. Without banners it is
# the first colour.
SPECTRUM = ("redprint", "orangeprint", "yellowprint", "greenprint", "tealprint", "blueprint", "indigoprint",
            "purpleprint", "pinkprint")
RAINBOW = "rainbowprint"
BANNERS_LOCK = Path(".github") / "banners.lock.json"


def rainbow_shade(root: Path) -> str:
    """The print a `rainbowprint` plate is drawn in now: the colour the banners
    beside it are in, else the first of the spectrum."""
    import json
    try:
        colour = json.loads((root / BANNERS_LOCK).read_text(encoding="utf-8")).get("rainbow")
    except (OSError, ValueError, AttributeError):
        colour = None
    return colour if colour in SPECTRUM else SPECTRUM[0]


# A live plate's value block takes the print its state names. Yellow is drawn
# in the orangeprint: a mustard block beside the gold sheet reads as one
# colour, and a state that cannot be told from its label is no signal.
STATE_PRINT = {"green": "greenprint", "yellow": "orangeprint",
               "red": "redprint", "slate": "blackprint"}

# What a twin letters with, per base style: (size, letter-spacing), in px.
# Everything else - height, padding, icon, gap, corner, sheen and case - is
# the base style's own, so swapping a style for its twin never moves a row.
_BLUEPRINT_TYPE = {
    "for-the-badge": (11.0, 1.3),
    "flat": (11.5, 0.35),
    "flat-square": (11.5, 0.35),
    "plastic": (11.0, 0.3),
    "pill": (11.5, 0.35),
    "compact": (9.5, 0.25),
}
BLUEPRINT_STYLES = {
    BLUEPRINT + key: dict(base=key, size=size, ls=ls,
                          **{k: STYLES[key][k] for k in
                             ("h", "pad", "icon", "gap", "rx", "sheen", "caps")})
    for key, (size, ls) in _BLUEPRINT_TYPE.items()
}
DEFAULT_BLUEPRINT = BLUEPRINT + DEFAULT_STYLE

# The two finishes again, in palette tokens: white for the light, ash and
# black for the fall, so a plate carries no colour outside the family.
BLUEPRINT_SHEENS = {
    "soft": (("0", "white", ".1"), ("1", "black", ".1")),
    "deep": (("0", "white", ".7"), (".1", "ash", ".1"),
             (".9", "black", ".3"), ("1", "black", ".5")),
}

GLYPHS_FILE = KIT_DIR / "fonts" / "barlow-condensed.json"
# Two cuts: SemiBold (`meta`) letters the label, Bold (`num`) the value. The
# letter is the glyph id's prefix, and neither is a hex digit, so an id can
# never read as a colour.
_FACE_ID = {"meta": "m", "num": "n"}
_GLYPHS: dict | None = None


def _faces() -> dict:
    """The glyph outlines, read once, on first use: a classic render never
    needs them, so a kit without the file still draws every classic badge."""
    global _GLYPHS
    if _GLYPHS is None:
        import json
        _GLYPHS = json.loads(GLYPHS_FILE.read_text(encoding="utf-8"))
    return _GLYPHS


def _glyph(font: dict, ch: str) -> str | None:
    """The glyph that draws `ch`: its own, else its capital, else None."""
    if ch in font["g"]:
        return ch
    up = ch.upper()
    return up if up in font["g"] else None


def missing_glyphs(text: str, face: str = "meta") -> str:
    """The characters of `text` the blueprint lettering cannot draw, once each."""
    font = _faces()[face]
    out = ""
    for ch in text:
        if _glyph(font, ch) is None and ch not in out:
            out += ch
    return out


def _bp_width(text: str, face: str, size: float, ls: float) -> float:
    """Advance width of `text` at `size`, with `ls` between glyphs."""
    font = _faces()[face]
    sc = size / font["upem"]
    total = sum(font["g"][_glyph(font, ch)][1] * sc for ch in text)
    return total + ls * max(len(text) - 1, 0)


def _fx(v: float, places: int = 3) -> str:
    """`v` to at most `places` decimals, trailing zeros dropped. Rounds an
    integer rather than using a format spec, the way banners does, so a near
    tie at the last place comes out the same on every Python."""
    n = round(v * 10 ** places)
    digits = str(abs(n)).rjust(places + 1, "0")
    head, tail = digits[:-places], digits[-places:].rstrip("0")
    return ("-" if n < 0 else "") + head + ("." + tail if tail else "")


def _f1(v: float) -> str:
    return _fx(v, 1)


class _Lettering:
    """Collects the glyphs one plate uses, so each is embedded once."""

    def __init__(self, uid: str) -> None:
        self.uid = uid
        self.used: set[tuple[str, str]] = set()

    def run(self, s: str, *, face: str, size: float, x: float, y: float,
            ls: float, fill: str, middle: bool = False) -> str:
        """A run of outlined glyphs with its baseline at `y`, starting at `x`
        or centred on it."""
        if not s:
            return ""
        font = _faces()[face]
        sc = size / font["upem"]
        x0 = x - _bp_width(s, face, size, ls) / 2 if middle else x
        adv, uses = 0.0, []
        for ch in s:
            key = _glyph(font, ch)
            if key != " ":
                self.used.add((face, key))
                uses.append(f'<use href="#{_FACE_ID[face]}{ord(key)}-{self.uid}" '
                            f'x="{round(adv)}"/>')
            adv += font["g"][key][1] + ls / sc
        return (f'<g transform="translate({_f1(x0)} {_f1(y)}) '
                f'scale({_fx(sc, 5)} {_fx(-sc, 5)})" fill="{fill}">'
                + "".join(uses) + "</g>")

    def defs(self) -> str:
        return "".join(
            f'<path id="{_FACE_ID[face]}{ord(ch)}-{self.uid}" d="{_faces()[face]["g"][ch][0]}"/>'
            for face, ch in sorted(self.used, key=lambda k: (k[0], ord(k[1]))))


def _block(left: float, w: int, h: float, rx: float) -> str:
    """The value's block: square on the label side, the style's corner on the
    outer one, and the whole plate when there is no label."""
    if left <= 0:
        return (f'<rect width="{w}" height="{_fx(h)}"'
                + (f' rx="{_fx(rx)}"' if rx else "") + ' fill="{fill}"/>')
    if not rx:
        return f'<path d="M{_f1(left)} 0H{w}V{_fx(h)}H{_f1(left)}Z" fill="{{fill}}"/>'
    return (f'<path d="M{_f1(left)} 0H{_f1(w - rx)}a{_fx(rx)} {_fx(rx)} 0 0 1 {_fx(rx)} '
            f'{_fx(rx)}V{_f1(h - rx)}a{_fx(rx)} {_fx(rx)} 0 0 1 {_fx(-rx)} {_fx(rx)}'
            f'H{_f1(left)}Z" fill="{{fill}}"/>')


def _plate(label: str, message: str, icon: str | None, style: str,
           reserve: tuple[str, ...], col: dict, seed: str) -> str:
    """Draw one plate in the colours `col` names (palette tokens):
    paper, wash (or None), grid and its opacity, block, ink (label and icon),
    letters (the value), frame and its opacity."""
    if style not in BLUEPRINT_STYLES:
        raise BadgeError(f"unknown blueprint style {style!r} - one of "
                         f"{', '.join(BLUEPRINT_STYLES)}")
    if icon is not None and icon != "" and icon not in ICONS:
        raise BadgeError(f"unknown icon {icon!r} - list the registry with --icons")
    g = BLUEPRINT_STYLES[style]
    aria = f"{label}: {message}" if label and message else (label or message)
    caps = (lambda s: s.upper()) if g["caps"] else (lambda s: s)
    text, vals = caps(label), [caps(v) for v in (message, *reserve)]
    for face, s in (("meta", text), *(("num", v) for v in vals)):
        gap = missing_glyphs(s, face)
        if gap:
            raise BadgeError(f"the blueprint lettering cannot draw {gap!r} in {s!r}")
    size, ls, pad, h, rx = g["size"], g["ls"], g["pad"], g["h"], g["rx"]
    has = bool(icon)
    iw = (g["icon"] + (g["gap"] if text else 0)) if has else 0.0
    left = (pad + iw + _bp_width(text, "meta", size, ls) + pad) if (text or has) else 0.0
    vw = (max(_bp_width(v, "num", size, ls) for v in vals) + 2 * pad) if any(vals) else 0.0
    w = round(left + vw)
    uid = hashlib.md5(seed.encode()).hexdigest()[:6]
    hx = lambda token: PALETTE[token]
    corner = f' rx="{_fx(rx)}"' if rx else ""
    whole = f'width="{w}" height="{_fx(h)}"{corner}'

    lt = _Lettering(uid)
    defs = [f'<pattern id="p{uid}" width="10" height="10" patternUnits="userSpaceOnUse">'
            f'<path d="M10 .5H.5V10" fill="none" stroke="{hx(col["grid"])}" '
            f'stroke-opacity="{col["grid_op"]}"/></pattern>']
    body = [f'<rect {whole} fill="{hx(col["paper"])}"/>']
    if col["wash"]:
        # A print by day is never quite white: the faintest wash of its line.
        body.append(f'<rect {whole} fill="{hx(col["wash"])}" fill-opacity=".03"/>')
    body.append(f'<rect {whole} fill="url(#p{uid})"/>')
    if vw:
        body.append(_block(left, w, h, rx).replace("{fill}", hx(col["block"])))
    if g["sheen"]:
        stops = "".join(f'<stop offset="{o}" stop-color="{hx(t)}" stop-opacity="{a}"/>'
                        for o, t, a in BLUEPRINT_SHEENS[g["sheen"]])
        defs.append(f'<linearGradient id="g{uid}" x2="0" y2="1">{stops}</linearGradient>')
        body.append(f'<rect {whole} fill="url(#g{uid})"/>')
    # The label's cap height sits on the plate's centre line, and the value
    # shares its baseline, so the two read as one line of lettering.
    font = _faces()["meta"]
    base = h / 2 + font["cap"] * size / font["upem"] / 2
    if has:
        body.append(f'<g transform="translate({_f1(pad)} {_f1((h - g["icon"]) / 2)}) '
                    f'scale({_fx(g["icon"] / 24, 4)})" fill="none" stroke="{hx(col["ink"])}" '
                    f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                    f'{ICONS[icon]}</g>')
    body.append(lt.run(text, face="meta", size=size, x=pad + iw, y=base, ls=ls,
                       fill=hx(col["ink"])))
    body.append(lt.run(vals[0], face="num", size=size, x=left + vw / 2, y=base, ls=ls,
                       fill=hx(col["letters"]), middle=True))
    body.append(f'<rect x=".5" y=".5" width="{w - 1}" height="{_fx(h - 1)}"'
                + (f' rx="{_fx(max(rx - .5, 0))}"' if rx else "")
                + f' fill="none" stroke="{hx(col["frame"])}" stroke-opacity="{col["frame_op"]}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{_fx(h)}" '
        f'viewBox="0 0 {w} {_fx(h)}" role="img" aria-label="{escape(aria)}">'
        f'<!--badge-kit v{KIT_VERSION}-->'
        f'<title>{escape(aria)}</title><defs>{"".join(defs)}{lt.defs()}</defs>'
        + "".join(body) + "</svg>"
    )


def render_blueprint(label: str, message: str, icon: str | None = None,
                     style: str = DEFAULT_BLUEPRINT, tone: str = DEFAULT_PRINT,
                     dark: bool = False, reserve: tuple[str, ...] = ()) -> str:
    """A static plate: the label on the print's drafting paper, the value on a
    block of the print. `tone` is a key of PRINTS; `dark` draws the night
    file. `reserve` sizes the value block for the widest of these values too,
    so a value that changes keeps the plate the same width."""
    if tone not in PRINTS:
        raise BadgeError(f"unknown print {tone!r} - one of {', '.join(PRINTS)}")
    p = PRINTS[tone]
    night = p.get("night", "white")
    if dark:
        col = dict(paper=p["sheet"], wash=None, grid=night, grid_op=".085",
                   block=night, ink=night, letters=p["sheet"], frame=night, frame_op=".9")
    else:
        col = dict(paper="white", wash=p["line"], grid=p["line"], grid_op=".08",
                   block=p["line"], ink=p["ink"], letters="white", frame=p["line"],
                   frame_op=".9")
    seed = f"{label}|{message}|{icon}|{style}|{tone}|{dark}|{'|'.join(reserve)}"
    return _plate(label, message, icon, style, tuple(reserve), col, seed)


def _state(token: str) -> str:
    """The health token a message colour names, whether written as the token
    or as its hex, so a live plate and validate() agree on what is legal."""
    want = PALETTE.get(token, token).upper()
    for tok in sorted(HEALTH_COLORS | HEALTH_NEUTRAL):
        if PALETTE[tok].upper() == want:
            return tok
    raise BadgeError(f"a live plate's state must be one of "
                     f"{', '.join(sorted(HEALTH_COLORS | HEALTH_NEUTRAL))}, not {token!r}")


def render_live(label: str, message: str, icon: str | None = None,
                style: str = DEFAULT_BLUEPRINT, state: str = "green",
                reserve: tuple[str, ...] = ()) -> str:
    """A live plate: the label on a gold sheet, the value on a block of the
    state's print. One file serves both themes."""
    p = PRINTS[STATE_PRINT[_state(state)]]
    col = dict(paper="gold", wash=None, grid="black", grid_op=".12", block=p["line"],
               ink="black", letters=p.get("night", "white"), frame="black", frame_op=".35")
    seed = f"{label}|{message}|{icon}|{style}|live|{_state(state)}|{'|'.join(reserve)}"
    return _plate(label, message, icon, style, tuple(reserve), col, seed)


# --------------------------------------------------------------------------- #
# Data file
# --------------------------------------------------------------------------- #
def load_badges(path: Path) -> list[dict]:
    """Parse the badge data file. Uses PyYAML when available; otherwise a tiny
    reader for the flat `badges:` list-of-maps schema (so `make badges` runs on
    a bare Python with no dependency)."""
    text = path.read_text(encoding="utf-8")

    def normalize(entries):
        # Both parsers land on the same shape: every value a string, None
        # (an empty `key:` line, or an unquoted `#hex` YAML swallowed as a
        # comment) becomes "", so PyYAML and the fallback always agree. A
        # list (`reserve: [Passing, Failing]`) joins with ", ", which is what
        # the fallback reads the same line as once its brackets are dropped.
        def scalar(v):
            if v is None:
                return ""
            if isinstance(v, list):
                return ", ".join("" if x is None else str(x) for x in v)
            return str(v)
        return [{str(k): scalar(v) for k, v in e.items()}
                for e in entries if isinstance(e, dict)]

    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
        return normalize(list(data.get("badges") or []))
    except ImportError:
        pass
    items: list[dict] = []
    cur: dict | None = None
    in_badges = False
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s == "badges:":
            in_badges = True
            continue
        # A new top-level key ends the badges list - never absorb another
        # section's items as phantom badges.
        if in_badges and raw[:1] not in (" ", "\t", "-"):
            break
        if not in_badges:
            continue
        if s.startswith("- "):
            cur = {}
            items.append(cur)
            s = s[2:].strip()
        if cur is None or ":" not in s:
            continue
        key, _, val = s.partition(":")
        val = val.strip()
        if val[:1] in ("'", '"'):
            # Quoted scalar: take the quoted run (with '' as an escaped
            # quote inside single quotes) and drop any trailing comment,
            # exactly as YAML does.
            q = val[0]
            body, i = [], 1
            while i < len(val):
                if val[i] == q:
                    if q == "'" and val[i + 1:i + 2] == "'":
                        body.append("'")
                        i += 2
                        continue
                    break
                body.append(val[i])
                i += 1
            val = "".join(body)
        elif " #" in val:
            val = val.split(" #", 1)[0].strip()
        cur[key.strip()] = val
    return normalize(items)


def validate(badges: list[dict]) -> list[str]:
    """Refuse silently-wrong definitions: bad names, colors, icons, styles."""
    errors: list[str] = []
    seen: set[str] = set()
    for i, b in enumerate(badges):
        name = str(b.get("name") or "")
        where = f"badges[{i}]" + (f" ({name})" if name else "")
        if not name:
            errors.append(f"{where}: missing 'name'")
            continue
        if not _NAME_RE.match(name):
            errors.append(f"{where}: name must be kebab-case ([a-z0-9-])")
        if name in seen:
            errors.append(f"{where}: duplicate name")
        seen.add(name)
        if not str(b.get("label", "")) and not str(b.get("message", "")):
            errors.append(f"{where}: needs a label or a message")
        style = str(b.get("style", DEFAULT_STYLE))
        if style not in STYLES and style not in BLUEPRINT_STYLES:
            errors.append(f"{where}: unknown style {style!r} (one of "
                          f"{', '.join([*STYLES, *BLUEPRINT_STYLES])})")
        errors.extend(f"{where}: {e}" for e in _blueprint_errors(b, style))
        icon = b.get("icon")
        if icon not in (None, "") and icon not in ICONS:
            errors.append(f"{where}: unknown icon {icon!r} (see --icons)")
        for field in ("label_color", "message_color"):
            tok = str(b.get(field) or ("black" if field == "label_color" else "blue"))
            if tok not in PALETTE and not _HEX_COLOR.match(tok):
                errors.append(
                    f"{where}: unknown color {tok!r} for {field} "
                    f"(palette token or #RRGGBB)"
                )
        # Dynamic-health rule: a gold-label badge uses color to signal a
        # STATUS, so its message must be a traffic-light color
        # (red/yellow/green) - or the reserved slate for an explicit "no
        # status yet" - never an arbitrary hue. (Document Styling: Badge
        # Health Colors.)
        lc = str(b.get("label_color") or "black")
        if _is_gold(lc):
            mc = str(b.get("message_color") or "blue")
            mc_hex = PALETTE.get(mc, mc).upper()
            allowed = {PALETTE[t].upper() for t in (HEALTH_COLORS | HEALTH_NEUTRAL)}
            if mc_hex not in allowed:
                errors.append(
                    f"{where}: a dynamic-health badge (gold label) must paint its "
                    f"message with a traffic-light color - "
                    f"{', '.join(sorted(HEALTH_COLORS))} (or slate for no status "
                    f"yet) - not {mc!r}"
                )
    # A static plate also writes `<name>-dark.svg`, so a badge named that
    # would be drawn over by it, or draw over it. Names are unique already;
    # this is the one way two entries can still claim one file.
    claimed: dict[str, str] = {}
    for b in badges:
        name = str(b.get("name") or "")
        if not name:
            continue
        for rel in paths_for(b):
            other = claimed.setdefault(rel, name)
            if other != name:
                errors.append(f"{other} and {name} both write {rel} - rename one "
                              f"(a static blueprint plate also writes <name>-dark.svg)")
    return errors


def _reserve(b: dict) -> tuple[str, ...]:
    """The values a plate reserves room for: `reserve: Passing, Failing`, or
    the same as a YAML flow list, `[Passing, Failing]`."""
    raw = str(b.get("reserve") or "").strip()
    if raw[:1] == "[" and raw[-1:] == "]":
        raw = raw[1:-1]
    return tuple(v.strip().strip("'\"") for v in raw.split(",") if v.strip())


def _is_blueprint(b: dict) -> bool:
    return str(b.get("style", DEFAULT_STYLE)) in BLUEPRINT_STYLES


def _blueprint_errors(b: dict, style: str) -> list[str]:
    """What a plate refuses that a classic badge does not, and the two fields
    only a plate has. A static plate is drawn in its print, so a message
    colour would be ignored; a live plate is drawn in its state's print, so a
    print would be. Either way the field is an error, not a silent no-op."""
    tone, reserve = str(b.get("print") or ""), _reserve(b)
    if style not in BLUEPRINT_STYLES:
        return ([f"'print' is for a blueprint style, not {style!r}"] if tone else []) + (
            [f"'reserve' is for a blueprint style, not {style!r}"] if reserve else [])
    out = []
    lc = str(b.get("label_color") or "black")
    if _is_gold(lc):
        if tone:
            out.append("a live plate (gold label) is drawn in its state's print - "
                       "drop 'print' and set message_color to "
                       f"{', '.join(sorted(HEALTH_COLORS))} or slate")
    else:
        if PALETTE.get(lc, lc).upper() != PALETTE["black"].upper():
            out.append(f"a blueprint plate's label is black (static) or gold (live), "
                       f"not {lc!r}")
        if str(b.get("message_color") or ""):
            out.append("a static blueprint plate is drawn in its print - drop "
                       "message_color and name one with 'print' "
                       f"({', '.join(PRINTS)})")
        if tone and tone != RAINBOW and tone not in PRINTS:
            out.append(f"unknown print {tone!r} (one of {', '.join(PRINTS)}, or {RAINBOW})")
    caps = BLUEPRINT_STYLES[style]["caps"]
    for field, face, text in (("label", "meta", str(b.get("label", ""))),
                              ("message", "num", str(b.get("message", ""))),
                              *(("reserve", "num", v) for v in reserve)):
        gap = missing_glyphs(text.upper() if caps else text, face)
        if gap:
            out.append(f"{field} {text!r} has characters the blueprint lettering "
                       f"cannot draw: {gap!r}")
    return out


def paths_for(b: dict) -> list[str]:
    """The files a badge writes, relative to the badge tree: one, or a day
    and a night file for a static plate. Rendering nothing, so the codemod can
    ask which files are this repository's own without drawing them."""
    sub, name = _dir_for(b), str(b["name"])
    if _is_blueprint(b) and sub == "static":
        return [f"static/{name}.svg", f"static/{name}-dark.svg"]
    return [f"{sub}/{name}.svg"]


def files_for(b: dict, rainbow: str = SPECTRUM[0], theme: str = "") -> dict[str, str]:
    """{relative path: file content} for one validated badge.

    A `theme` draws a static plate in that print instead of the one it names,
    so one choice colours a whole page. A live plate keeps its state's print
    and a classic badge its colours: theirs mean something.
    """
    paths = paths_for(b)
    if not _is_blueprint(b):
        return {paths[0]: _svg_for(b) + "\n"}
    label, message = str(b.get("label", "")), str(b.get("message", ""))
    icon, style, reserve = b.get("icon") or None, str(b["style"]), _reserve(b)
    if _dir_for(b) == "dynamic":
        return {paths[0]: render_live(label, message, icon, style,
                                      str(b.get("message_color") or ""), reserve) + "\n"}
    tone = theme or str(b.get("print") or DEFAULT_PRINT)
    if tone == RAINBOW:
        tone = rainbow   # the colour the banners are in now, resolved once per run by the caller
    return {rel: render_blueprint(label, message, icon, style, tone, dark, reserve) + "\n"
            for rel, dark in zip(paths, (False, True))}


def _svg_for(b: dict) -> str:
    return render(
        str(b.get("label", "")), str(b.get("message", "")),
        str(b.get("label_color", "black")), str(b.get("message_color", "blue")),
        b.get("icon") or None, str(b.get("style", DEFAULT_STYLE)),
    )


def _is_gold(token: str) -> bool:
    """True for the dynamic-health label, whether written as the palette
    token or as its raw hex - validate() and the folder routing must agree."""
    return PALETTE.get(token, token).upper() == PALETTE["gold"].upper()


def _svg_for_kwargs(kw: dict) -> str:
    """Render from gallery_specs() kwargs (label/message/colors/icon/style,
    and for a plate its print and theme, or its state)."""
    style = kw.get("style", DEFAULT_STYLE)
    if style in BLUEPRINT_STYLES:
        if kw.get("state"):
            return render_live(kw.get("label", ""), kw.get("message", ""),
                               kw.get("icon"), style, kw["state"])
        return render_blueprint(kw.get("label", ""), kw.get("message", ""),
                                kw.get("icon"), style,
                                kw.get("print", DEFAULT_PRINT), kw.get("dark", False))
    return render(kw.get("label", ""), kw.get("message", ""),
                  kw.get("label_color", "black"), kw.get("message_color", "blue"),
                  kw.get("icon"), kw.get("style", DEFAULT_STYLE))


def _dir_for(b: dict) -> str:
    """Type subfolder for a badge under assets/badges/: 'dynamic' for the
    automation-refreshed health badges (gold label - build, last-commit,
    deploy, scorecard), 'static' for every fixed-value badge (black label)."""
    return "dynamic" if _is_gold(str(b.get("label_color") or "black")) else "static"


def _reserved_doc_badges(root: Path, data: Path, out: Path) -> set[str]:
    """Relative paths ('static/<name>.svg') of the doc-header classification
    badges: they share the static/ folder but are owned by
    scripts/localize-badges.py, so reserving them keeps this generator's
    orphan check and pruning from ever touching a badge it does not manage.
    Lazy + fail-open: if the sibling script is unavailable, reserve nothing -
    the badges.yml set still renders correctly."""
    try:
        import importlib.util
        loc = KIT_DIR / "localize-badges.py"
        spec = importlib.util.spec_from_file_location("localize_badges", loc)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return {f"static/{n}" for n in mod.managed_doc_filenames(root, data, out)}
    except Exception:
        return set()


_YAML_LEXICON = {"yes", "no", "on", "off", "true", "false", "null", "~"}


def _yaml_scalar(value: str) -> str:
    """Quote a scalar whenever YAML would read it as anything but text:
    special characters, leading digits/dashes, surrounding whitespace, and
    the YAML 1.1 boolean/null lexicon ('Yes' must stay 'Yes', not True)."""
    if (re.search(r"[:#'\"]|^\s|\s$|^[\d\-]", value) or value == ""
            or value.lower() in _YAML_LEXICON):
        return "'" + value.replace("'", "''") + "'"
    return value


def set_values(path: Path, updates: dict[str, tuple[str, str | None]]) -> list[str]:
    """Surgical value updates in badges.yml that PRESERVE comments and layout:
    for each `name: (message, color-or-None)`, rewrite that entry's `message:`
    line (and `message_color:` when a color is given - inserting the line
    after `message:` if the entry never had one) in place."""
    lines = path.read_text(encoding="utf-8").split("\n")
    cur = None
    done: set[str] = set()
    msg_line: dict[str, tuple[int, str]] = {}  # entry -> (index, indent)
    color_done: set[str] = set()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            continue
        m = re.match(r"\s*-\s+name:\s*['\"]?([A-Za-z0-9-]+)['\"]?\s*$", line)
        if m:
            cur = m.group(1)
            continue
        if cur not in updates:
            continue
        message, color = updates[cur]
        m2 = re.match(r"(\s*)message:\s*\S.*$", line)
        if m2:
            lines[i] = f"{m2.group(1)}message: {_yaml_scalar(message)}"
            done.add(cur)
            msg_line[cur] = (i, m2.group(1))
        if color:
            m3 = re.match(r"(\s*)message_color:\s*\S.*$", line)
            if m3:
                lines[i] = f"{m3.group(1)}message_color: {color}"
                color_done.add(cur)
    # A color update for an entry with no message_color line yet: insert one
    # right after the entry's message line (bottom-up, so indices hold).
    pending = [(idx, indent, updates[name][1]) for name, (idx, indent) in msg_line.items()
               if updates[name][1] and name not in color_done]
    for idx, indent, color in sorted(pending, reverse=True):
        lines.insert(idx + 1, f"{indent}message_color: {color}")
    missing = sorted(set(updates) - done)
    if not missing:
        path.write_text("\n".join(lines), encoding="utf-8")
    return missing


def randomize_static(path: Path, seed: str) -> list[tuple[str, str]]:
    """Recolor the DECORATIVE static badges from the non-status palette pool.

    A static badge (black label) that is NOT already painted a status color
    gets a message color deterministically picked from STATIC_RANDOM_POOL,
    keyed by (seed, name). Badges already using a traffic-light color
    (green/yellow/red) are "similar to a status badge" and left fixed - so
    Status stays green, License yellow, Security red - and dynamic-health
    (gold-label) badges are never touched. The seed is the caller's to
    choose: the Badge Refresh workflow passes the ISO week, so the colors
    rotate weekly and are stable within a week (re-running mid-week is a
    clean no-op, and --check stays valid). Preserves comments and layout by
    writing through set_values. Returns the (name, new_color) pairs changed.
    """
    # Semantic colors are never rotated away: the traffic-light triad
    # (Status green, License yellow, Security red) plus the docs-law slot
    # colors (Role pink, Context purple) - see _RANDOM_RESERVED.
    fixed_hex = {PALETTE[t].upper() for t in HEALTH_COLORS} | {
        PALETTE["pink"].upper(),
        PALETTE["purple"].upper(),
    }
    black_hex = PALETTE["black"].upper()
    updates: dict[str, tuple[str, str | None]] = {}
    changed: list[tuple[str, str]] = []
    for b in load_badges(path):
        name = str(b.get("name") or "")
        if not name:
            continue
        if _is_blueprint(b):
            continue  # a plate is drawn in its print, and has no message color
        lc = str(b.get("label_color") or "black")
        if PALETTE.get(lc, lc).upper() != black_hex:
            continue  # dynamic-health (or non-black label) - never randomized
        mc = str(b.get("message_color") or "blue")
        if PALETTE.get(mc, mc).upper() in fixed_hex:
            continue  # a status or slot color - semantic, keep it fixed
        idx = int(hashlib.md5(f"{seed}:{name}".encode()).hexdigest(), 16) % len(STATIC_RANDOM_POOL)
        new_color = STATIC_RANDOM_POOL[idx]
        if PALETTE.get(mc, mc).upper() == PALETTE[new_color].upper():
            continue  # already that color this period
        updates[name] = (str(b.get("message", "")), new_color)
        changed.append((name, new_color))
    if updates:
        # set_values writes nothing when ANY targeted entry lacks a message
        # line (all-or-nothing), so a non-empty return means the file was NOT
        # written - do not claim a rotation that did not happen.
        if set_values(path, updates):
            return []
    return changed


# --------------------------------------------------------------------------- #
# Gallery - every icon and every color, drawn rather than listed.
#
# The registries above are the source of truth, so the gallery is GENERATED
# from them: add an icon to ICONS and it appears here on the next render,
# with no list for anyone to forget to update. That is the same reason
# --icons and --palette exist instead of a table in the docs.
#
# Gallery badges live in the ONE badge tree alongside everything else, under
# a `gallery-` prefix. They are not entries in the data file, so pruning
# would treat them as orphans: gallery_filenames() is reserved in main() for
# exactly that reason, the same mechanism that protects the codemod's
# classification badges.
# --------------------------------------------------------------------------- #
GALLERY_PREFIX = "gallery-"

# Themed groups for the gallery. Browsing 64 glyphs alphabetically means
# reading all of them to find the one you want; grouped, you read one row.
#
# This is the only hand-kept list in the kit, and it is DRIFT-SAFE by
# construction: the gallery computes the leftovers and prints them under
# "Everything else", so adding a glyph to ICONS without touching this still
# produces a correct page. A test asserts every icon appears exactly once.
ICON_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Status & health", ("pulse", "check", "check-circle", "cross", "alert",
                         "info", "question", "flag")),
    ("Security", ("shield", "lock", "key", "eye", "scale")),
    ("Code & build", ("code", "terminal", "commit", "branch", "gear", "wrench",
                      "bug", "flask", "chip")),
    ("Ship & run", ("rocket", "package", "cloud", "server", "database",
                    "download", "upload", "sync", "play")),
    ("Docs & data", ("book", "chart", "folder", "tag", "link", "grid",
                     "layers", "search")),
    ("People", ("users", "chat", "mail", "heart", "star", "medal", "trophy",
                "sparkle")),
    ("Time & place", ("clock", "calendar", "globe", "compass", "pin", "target",
                      "home", "bell")),
    ("Shapes & marks", ("flame", "bolt", "sun", "moon", "infinity", "plus",
                        "minus", "trash", "arrow")),
)


def _hue_sat_lum(hexc: str) -> tuple[float, float, float]:
    """Hue in degrees, saturation and lightness in 0..1, from #RRGGBB."""
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    mx, mn = max(r, g, b), min(r, g, b)
    lum = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, lum
    d = mx - mn
    sat = d / (2 - mx - mn) if lum > 0.5 else d / (mx + mn)
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60, sat, lum


# Hue bands for the color gallery, computed from the hex rather than listed,
# so a new token files itself. Anything under the saturation floor is neutral
# whatever its hue, which is what puts black, white and the greys together.
COLOR_BANDS: tuple[tuple[str, float, float], ...] = (
    ("Reds", 345.0, 15.0), ("Oranges", 15.0, 45.0), ("Yellows", 45.0, 70.0),
    ("Greens", 70.0, 165.0), ("Cyans & teals", 165.0, 200.0),
    ("Blues", 200.0, 255.0), ("Violets", 255.0, 290.0),
    ("Pinks & magentas", 290.0, 345.0),
)
NEUTRAL_SAT = 0.18


def color_families() -> list[tuple[str, list[str]]]:
    """(band name, tokens) with every token in exactly one band, ordered by
    hue then lightness so each row reads as a gradient."""
    neutral, banded = [], {name: [] for name, _, _ in COLOR_BANDS}
    for tok, hexc in PALETTE.items():
        h, s, l = _hue_sat_lum(hexc)
        if s < NEUTRAL_SAT:
            neutral.append((l, tok))
            continue
        for name, lo, hi in COLOR_BANDS:
            inside = (h >= lo or h < hi) if lo > hi else (lo <= h < hi)
            if inside:
                # The Reds band wraps past 360, so raw hue would sort the deep
                # reds after the orange ones and break the gradient exactly at
                # the seam. Unwrap to a continuous run before sorting.
                key = h - 360.0 if (lo > hi and h >= lo) else h
                banded[name].append((key, l, tok))
                break
    out = [(name, [tok for _, _, tok in sorted(banded[name])])
           for name, _, _ in COLOR_BANDS if banded[name]]
    out.append(("Neutrals", [tok for _, tok in sorted(neutral)]))
    return out
# A fixed, non-status hue for the icon row: the glyph is the subject, and a
# traffic-light color on 64 badges would read as 64 status signals.
GALLERY_ICON_COLOR = "indigo"


def combination_count() -> dict[str, int]:
    """How many visually distinct badges the registries can express.

    Counted, not asserted: the colour pairs are filtered through validate(),
    so the traffic-light rule's effect on the total is measured rather than
    assumed. Text is excluded, being free, which makes the real space
    unbounded; this is the space of everything EXCEPT the wording.
    """
    pairs = health = 0
    for lc in PALETTE:
        for mc in PALETTE:
            if validate([dict(name="x", label="A", message="B",
                              label_color=lc, message_color=mc)]):
                continue
            pairs += 1
            if _is_gold(lc):
                health += 1
    icons = len(ICONS) + 1          # every glyph, plus none at all
    styles = len(STYLES)
    # The plates are counted on their own: a plate takes a print or a state
    # rather than a colour pair, so it is a second space, not more of the
    # first, and the classic total stays what it counts.
    plates = len(PRINTS) * icons * len(BLUEPRINT_STYLES)
    live = len(HEALTH_COLORS | HEALTH_NEUTRAL) * icons * len(BLUEPRINT_STYLES)
    return {
        "pairs": pairs,
        "refused": len(PALETTE) ** 2 - pairs,
        "icons": icons,
        "styles": styles,
        "total": pairs * icons * styles,
        "health": health * icons * styles,
        "static": (pairs - health) * icons * styles,
        "plates": plates,
        "live_plates": live,
        "blueprint": plates + live,
    }


def gallery_specs() -> list[tuple[str, dict]]:
    """(basename, render kwargs) for every gallery badge.

    An icon badge puts the glyph and its own name in the label, so the thing
    you look at and the thing you type are the same badge. A color badge is
    painted in the token and carries its hex, which also demonstrates the ink
    flip: dark text lands on the light tokens, white on the dark ones.
    """
    out: list[tuple[str, dict]] = []
    for name in sorted(ICONS):
        out.append((f"{GALLERY_PREFIX}icon-{name}", dict(
            label=name, message="", label_color="black",
            message_color=GALLERY_ICON_COLOR, icon=name)))
    for tok in sorted(PALETTE):
        out.append((f"{GALLERY_PREFIX}color-{tok}", dict(
            label=tok, message=PALETTE[tok], label_color="black",
            message_color=tok, icon=None)))
    for style in STYLES:
        out.append((f"{GALLERY_PREFIX}style-{style}", dict(
            label="style", message=style, label_color="black",
            message_color="steel", icon="sparkle", style=style)))
    for tok in sorted(HEALTH_COLORS | HEALTH_NEUTRAL):
        out.append((f"{GALLERY_PREFIX}health-{tok}", dict(
            label="health", message=tok, label_color="gold",
            message_color=tok, icon="pulse")))
    # The plates. A static plate is a pair, day and `-dark`, the way a
    # consumer's is; a live plate is one file.
    for key in BLUEPRINT_STYLES:
        for dark in (False, True):
            out.append((f"{GALLERY_PREFIX}{key}" + ("-dark" if dark else ""), dict(
                label="style", message=key, icon="sparkle", style=key, dark=dark)))
        out.append((f"{GALLERY_PREFIX}{key}-live", dict(
            label="live", message=key, icon="pulse", style=key, state="green")))
    for tone in PRINTS:
        for dark in (False, True):
            out.append((f"{GALLERY_PREFIX}print-{tone}" + ("-dark" if dark else ""), dict(
                label="print", message=tone, icon="layers", style=DEFAULT_BLUEPRINT,
                print=tone, dark=dark)))
    for tok in sorted(STATE_PRINT):
        out.append((f"{GALLERY_PREFIX}state-{tok}", dict(
            label="state", message=tok, icon="pulse", style=DEFAULT_BLUEPRINT,
            state=tok)))
    return out


def gallery_filenames() -> set[str]:
    """Basenames the gallery owns. Reserved from pruning, and treated as this
    repository's own badges by the codemod so their references stay relative."""
    return {f"{stem}.svg" for stem, _ in gallery_specs()}


def _grid(rows: list[str], per_row: int) -> str:
    """Badges laid out N per line. Markdown joins images on one line into a
    single row, and a blank line starts the next, so this is the whole trick."""
    out = []
    for i in range(0, len(rows), per_row):
        out.append("\n".join(rows[i:i + per_row]))
    return "\n\n".join(out)


def _anchor(title: str) -> str:
    """GitHub's heading anchor: lowercase, non-alphanumerics dropped, spaces
    to hyphens. Used so the contents table actually links."""
    return "#" + re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-")


def gallery_markdown(rel: str) -> str:
    """The gallery page, generated whole. `rel` is the badge tree's path
    relative to the document, so the images resolve from docs/."""
    def img(stem: str, alt: str) -> str:
        return f"![{alt}]({rel}/static/{stem}.svg)"

    def icon_row(names) -> str:
        return _grid([img(f"{GALLERY_PREFIX}icon-{n}", f"The {n} icon")
                      for n in names], 4)

    def color_row(toks) -> str:
        return _grid([img(f"{GALLERY_PREFIX}color-{t}",
                          f"The {t} color token, {PALETTE[t]}") for t in toks], 4)

    grouped = {i for _, g in ICON_GROUPS for i in g}
    icon_sections = list(ICON_GROUPS)
    leftover = sorted(set(ICONS) - grouped)
    if leftover:
        icon_sections.append(("Everything else", tuple(leftover)))

    families = color_families()

    icons_md = "\n\n".join(
        f"#### {title}\n\n{icon_row(names)}" for title, names in icon_sections)
    colors_md = "\n\n".join(
        f"#### {title}\n\n{color_row(toks)}" for title, toks in families)

    icon_toc = " &middot; ".join(
        f"[{title}]({_anchor(title)})" for title, _ in icon_sections)
    color_toc = " &middot; ".join(
        f"[{title}]({_anchor(title)})" for title, _ in families)

    style_sections = [(title, blurb, names) for title, blurb, names in STYLE_GROUPS]
    ungrouped = [s for s in STYLES
                 if s not in {x for _, _, g in STYLE_GROUPS for x in g}]
    if ungrouped:
        style_sections.append(("Everything else", "", tuple(ungrouped)))
    styles = "\n\n".join(
        f"#### {title}\n\n{blurb}\n\n" + "\n".join(
            img(f"{GALLERY_PREFIX}style-{s}", f"The {s} style") for s in names)
        if blurb else
        f"#### {title}\n\n" + "\n".join(
            img(f"{GALLERY_PREFIX}style-{s}", f"The {s} style") for s in names)
        for title, blurb, names in style_sections)
    health = "\n".join(
        img(f"{GALLERY_PREFIX}health-{t}", f"A health badge in {t}")
        for t in sorted(HEALTH_COLORS | HEALTH_NEUTRAL))

    def pic(stem: str, alt: str) -> str:
        # A static plate's pair, the way a consumer embeds one: the night
        # file for a dark theme, the day file for everything else.
        return (f'<picture><source media="(prefers-color-scheme: dark)" '
                f'srcset="{rel}/static/{stem}-dark.svg">'
                f'<img alt="{alt}" src="{rel}/static/{stem}.svg"></picture>')

    plate_rows = "\n\n".join(
        pic(f"{GALLERY_PREFIX}{key}", f"The {key} style") + "\n"
        + img(f"{GALLERY_PREFIX}{key}-live", f"The {key} style, live")
        for key in BLUEPRINT_STYLES)
    prints = _grid([pic(f"{GALLERY_PREFIX}print-{t}", f"The {t}") for t in PRINTS], 3)
    states = "\n".join(
        img(f"{GALLERY_PREFIX}state-{t}", f"A live plate in {t}, drawn in the {STATE_PRINT[t]}")
        for t in sorted(STATE_PRINT))

    return f"""<!--
title: '\U0001F3A8 GALLERY'
description: 'Every icon, color token and style the Badge Kit can draw, rendered rather than listed.'
tags: [badges, icons, palette, reference]
category: docs
-->

<!-- markdownlint-disable MD041 -->
<!-- GENERATED BY src/badge-kit.py --gallery. Do not edit by hand: run `make gallery`. -->

<div align="center">

# \U0001F3A8 GALLERY

<a name="top"></a>

**Everything the kit can draw, drawn.**

_Pick by eye, copy the name._

</div>

---

## \U0001F9ED Contents

| Section | Count | What the name is for |
| :--- | ---: | :--- |
| [\U0001F58B️ Icons](#️-icons) | {len(ICONS)} | The value of `icon:` |
| [\U0001F3A8 Color tokens](#-color-tokens) | {len(PALETTE)} | The value of `label_color:` or `message_color:` |
| [\U0001F9F1 Styles](#-styles) | {len(STYLES)} | The value of `style:` |
| [\U0001F6A6 Health colors](#-health-colors) | {len(HEALTH_COLORS | HEALTH_NEUTRAL)} | What a gold label may paint its message |
| [\U0001F4D0 Blueprint plates](#-blueprint-plates) | {len(BLUEPRINT_STYLES)} | The value of `style:` for a plate |
| [\U0001F5A8️ Prints](#️-prints) | {len(PRINTS)} | The value of `print:` |

Every badge below carries its own name, so the thing you look at and the thing
you type are the same badge. Nothing on this page is fetched: each one is a
committed SVG in this repository.

Combined, these make **{combination_count()["total"]:,} visually distinct
badges** before you have written a single word of label or message, which is
what makes the real number unbounded. Of those, {combination_count()["static"]:,}
are static and only {combination_count()["health"]:,} are health badges: the
traffic-light rule refuses {combination_count()["refused"]} of the
{len(PALETTE) ** 2} colour pairs, which is why a status signal has almost no
room to be creative in.

---

## \U0001F58B️ Icons

{len(ICONS)} line glyphs on a 24x24 grid, stroked in the label's ink color so
they read on any background. Grouped by what they are for, because reading 64
alphabetically to find one is not browsing.

{icon_toc}

{icons_md}

---

## \U0001F3A8 Color Tokens

{len(PALETTE)} tokens, one per icon, tuned to a single saturation and lightness
family so any two sit together without clashing. Each was checked against every
other and clears the palette's own minimum spacing, so no two read as the same
color. A raw `#RRGGBB` works anywhere a token does.

Grouped by hue and ordered within each group, so a row reads as a gradient and
you can pick a neighbour when one is not quite right. Watch the ink flip to
dark on the light tokens: that is chosen by luminance, not from a list.

{color_toc}

{colors_md}

---

## \U0001F9F1 Styles

The same badge {len(STYLES)} ways, grouped by the job you are picking one for.
`for-the-badge` is the default. A style is geometry and nothing else: a corner
radius, an optional overlay gradient, and a scale applied to the metric
tables, so every one of these measures its text exactly rather than
approximately.

{styles}

---

## \U0001F6A6 Health Colors

A **gold label** marks a value that changes over time, so its color has to mean
something. The message is restricted to these, and any other hue on a gold
label is rejected at render time rather than quietly drawn.

{health}

---

## \U0001F4D0 Blueprint Plates

Every style again, drawn the way
[`tannergolden/banners`](https://github.com/tannergolden/banners) draws a
header: the label lettered on drafting paper, the value on a solid block of the
print, and the plate framed in the print's line. Each keeps its style's height,
corner, padding and case, so swapping a style for its twin never moves a row.

The lettering is outlined Barlow Condensed, a path per glyph, so it looks the
same on every device. A static plate is two files, one for each theme GitHub
paints, and the day file is shown here unless your theme is dark. The live
plate beside each one is a gold label: its value is drawn in the state's
print, one file for either theme.

{plate_rows}

---

## \U0001F5A8️ Prints

A static plate's colour is its **print**, the colour a drawing is reproduced
in: its lines on white paper by day, and by night the sheet those lines are
printed on. `blueprint` is the default. These are the same eleven the banners
draw in, so a row of plates matches the banner above it. `rainbowprint` is
the colour the page's banners are in now, read from their lock, so a row of
plates changes colour with the header; without banners it is the redprint.

{prints}

A live plate takes no print. Its value is drawn in the print its state names,
and yellow is drawn in the orangeprint, since a mustard block beside the gold
sheet would read as one colour:

{states}

---

## \U0001F517 See also

> [!TIP]
> The schema these values go into is [`Badge-Kit.md`](Badge-Kit.md), and
> [`badges.example.yml`](badges.example.yml) is a starter file to copy.

---

<div align="center">

**Drawn from the registry, never transcribed.**

[↑ Back to Top](#top)

</div>
"""


# --------------------------------------------------------------------------- #
# Self-test - renderer and parser invariants, run by `make lint-docs`.
# --------------------------------------------------------------------------- #
def self_test() -> int:
    import tempfile
    import xml.dom.minidom as minidom

    checks = 0

    def ok(cond: bool, what: str) -> None:
        nonlocal checks
        checks += 1
        if not cond:
            raise AssertionError(f"badge-kit self-test failed: {what}")

    # Every style renders well-formed XML for tricky strings, and twice
    # identically (determinism is what --check relies on).
    for style in STYLES:
        for label, msg in (("Build Status", "Passing"), ("W%W", "100%"),
                           ("i", "6.6"), ("A&B", "<ok>"), ("Läuft", "λ")):
            svg = render(label, msg, "gold", "green", "pulse", style)
            minidom.parseString(svg)
            ok(svg == render(label, msg, "gold", "green", "pulse", style),
               f"deterministic {style}")
            ok(f"badge-kit v{KIT_VERSION}" in svg, "version stamp present")
    # Every icon in the registry embeds as well-formed markup.
    for name in ICONS:
        minidom.parseString(render("X", "Y", "black", "green", name))
        checks += 1
    # Golden render: changing rendered output requires bumping KIT_VERSION
    # and this hash together, consciously.
    golden = hashlib.sha256(
        render("Golden", "Path", "gold", "green", "pulse").encode()
    ).hexdigest()
    ok(golden == GOLDEN_SHA,
       f"rendered output changed (golden sha256 {golden}) - bump KIT_VERSION "
       f"and update GOLDEN_SHA in the same change")
    # Every plate: well-formed, deterministic, stamped, lettered in paths
    # rather than <text>, and every id it references is one it defines.
    for style in BLUEPRINT_STYLES:
        for label, msg in (("Build Status", "Passing"), ("W%W", "100%"),
                           ("i", "6.6"), ("A&B", "<ok>"), ("Läuft", "Ünïcödé"),
                           ("", "Value only"), ("Label only", "")):
            for svg in (render_blueprint(label, msg, "pulse", style),
                        render_blueprint(label, msg, None, style, "yellowprint", True),
                        render_live(label, msg, "pulse", style, "yellow", ("Failing",))):
                minidom.parseString(svg)
                ok(f"badge-kit v{KIT_VERSION}" in svg, "plate version stamp present")
                ok("<text" not in svg, "plate lettered in paths")
                ids = re.findall(r'\bid="([^"]+)"', svg)
                ok(len(ids) == len(set(ids)), f"plate ids unique in {style}")
                refs = set(re.findall(r'(?:href="#|url\(#)([^")]+)', svg))
                ok(refs <= set(ids), f"plate references only its own ids in {style}")
            ok(render_live(label, msg, "pulse", style, "green")
               == render_live(label, msg, "pulse", style, "green"),
               f"deterministic {style}")
    golden = hashlib.sha256("".join(
        (render_blueprint("Golden", "Path", "pulse"),
         render_blueprint("Golden", "Path", "pulse", dark=True),
         render_live("Golden", "Path", "pulse", state="green"))).encode()).hexdigest()
    ok(golden == GOLDEN_BLUEPRINT_SHA,
       f"plate output changed (golden sha256 {golden}) - bump KIT_VERSION and "
       f"update GOLDEN_BLUEPRINT_SHA in the same change")
    # A character the lettering lacks is refused, never drawn as a gap.
    try:
        render_blueprint("Status", "漢")
        ok(False, "a missing glyph must raise")
    except BadgeError:
        checks += 1
    ok(bool(validate([dict(name="x", label="A", message="漢",
                           style=DEFAULT_BLUEPRINT)])), "validate refuses a missing glyph")
    # Reserving a value widens the block to the widest; the plate never shrinks.
    wid = lambda svg: int(re.search(r'width="(\d+)"', svg).group(1))
    ok(wid(render_live("Build", "Failing", None, state="red", reserve=("Passing",)))
       == wid(render_live("Build", "Passing", None, state="green", reserve=("Failing",))),
       "reserve keeps a live plate one width")
    # The accessible name keeps the author's casing; display text is capped.
    svg = render("Build Status", "Passing", "gold", "green")
    ok('aria-label="Build Status: Passing"' in svg, "aria keeps original case")
    ok(">BUILD STATUS</text>" in svg, "display text uppercased")
    # YAML lexicon values survive --set quoting.
    ok(_yaml_scalar("Yes") == "'Yes'", "boolean-like scalar quoted")
    ok(_yaml_scalar("Passing") == "Passing", "plain scalar unquoted")
    # Metrics: wide glyphs really are wider, and width grows with length.
    wide = _text_width("WWW", _W_BOLD11, 11.0, 1.0)
    narrow = _text_width("III", _W_BOLD11, 11.0, 1.0)
    ok(wide > narrow, "W wider than I")
    ok(_text_width("AA", _W_BOLD11, 11.0, 1.0) > _text_width("A", _W_BOLD11, 11.0, 1.0),
       "width grows with length")
    # Ink contrast: dark text on light message colors, white on dark.
    ok(_ink(PALETTE["yellow"]) == "#1f2328", "dark ink on yellow")
    ok(_ink(PALETTE["black"]) == "#ffffff", "white ink on black")
    # Validation refuses what it must.
    for bad in (dict(name="x", label="A", message="B", icon="nope"),
                dict(name="x", label="A", message="B", message_color="gren"),
                dict(name="x", label="A", message="B", style="3d"),
                dict(name="BAD NAME", label="A", message="B"),
                # Traffic-light rule: a gold (dynamic-health) label may only
                # carry a health message color (green/yellow/red/slate).
                dict(name="x", label="A", message="B", label_color="gold", message_color="blue")):
        ok(bool(validate([bad])), f"validate rejects {bad}")
    # ...and it ACCEPTS a gold label with a health color.
    ok(validate([dict(name="x", label="A", message="B", label_color="gold", message_color="green")]) == [],
       "validate accepts gold + health color")
    ok(validate([dict(name="a", label="A", message="B"),
                 dict(name="a", label="A", message="B")]) != [], "duplicate name rejected")
    # The fallback parser agrees with PyYAML (when present) and --set keeps
    # comments while updating exactly the named entry's value.
    doc = ("# top comment\nbadges:\n"
           "  # entry comment\n"
           "  - name: build\n    label: Build Status\n    message: Passing\n"
           "    message_color: green\n    icon: check\n"
           "  - name: score\n    label: Score\n    message: '6.6' # quoted + comment\n"
           "  - name: bare\n    label: Bare\n    message: Value\n")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "badges.yml"
        p.write_text(doc, encoding="utf-8")
        parsed = load_badges(p)
        ok([b["name"] for b in parsed] == ["build", "score", "bare"],
           "parser reads entries")
        ok(str(parsed[1]["message"]) == "6.6",
           "quoted scalar with trailing comment preserved")
        missing = set_values(p, {"build": ("Failing", "red"),
                                 "score": ("7.1", None),
                                 "bare": ("Set", "green")})
        ok(missing == [], "--set finds every entry")
        after = p.read_text(encoding="utf-8")
        ok("# entry comment" in after and "# top comment" in after,
           "--set preserves comments")
        reparsed = load_badges(p)
        ok(str(reparsed[0]["message"]) == "Failing"
           and str(reparsed[0]["message_color"]) == "red"
           and str(reparsed[1]["message"]) == "7.1", "--set updates values")
        ok(str(reparsed[2].get("message_color")) == "green",
           "--set inserts message_color when the entry had none")
    print(f"✅ Badge kit self-test passed - {checks} checks.")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render self-hosted SVG badges.")
    ap.add_argument("--root", type=Path, default=None,
                    help="repository to render for (default: GITHUB_WORKSPACE, else "
                         "the working directory); --data and --out default under it")
    ap.add_argument("--data", type=Path, default=None,
                    help="badge data file (default: .github/badges.yml under --root)")
    ap.add_argument("--out", type=Path, default=None,
                    help="badge tree to render into (default: assets/badges under --root)")
    ap.add_argument("--check", action="store_true",
                    help="verify committed SVGs match the data file, write nothing")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=MESSAGE[:COLOR]",
                    help="update a badge's message (and optionally message color) "
                         "in the data file, then re-render (repeatable)")
    ap.add_argument("--randomize-static", metavar="SEED", default=None,
                    help="recolor the decorative static badges from the non-status "
                         "palette, keyed by SEED (the Badge Refresh workflow passes "
                         "the ISO week, so colors rotate weekly), then re-render")
    ap.add_argument("--theme", default="", metavar="PRINT",
                    help="draw every static plate in this print instead of the one it "
                         "names (rainbowprint follows the banners); live plates and "
                         "classic badges keep their colours")
    ap.add_argument("--icons", action="store_true", help="list the icon registry")
    ap.add_argument("--palette", action="store_true", help="list the palette tokens")
    ap.add_argument("--self-test", action="store_true",
                    help="run renderer and parser invariants")
    ap.add_argument("--markdown", action="store_true",
                    help="print a ready-to-paste Markdown embed line per badge "
                         "(alt text from label/message, wrapped in its link), "
                         "write nothing")
    ap.add_argument("--gallery", action="store_true",
                    help="render every icon, color token, style and health color "
                         "into the badge tree and regenerate the gallery page; "
                         "with --check, verify both are current")
    ap.add_argument("--gallery-page", type=Path, default=None,
                    help="gallery page to write (default: docs/Gallery.md under --root)")
    ap.add_argument("--version", action="version", version=f"badge-kit {KIT_VERSION}")
    args = ap.parse_args(argv)
    root = args.root.resolve() if args.root else REPO_ROOT
    if args.data is None:
        args.data = root / ".github" / "badges.yml"
    if args.out is None:
        args.out = root / "assets" / "badges"

    if args.gallery:
        page = args.gallery_page or (root / "docs" / "Gallery.md")
        dest = args.out / "static"
        # The page and the badges live at different depths, so the reference
        # is the tree relative to the PAGE, not to the repository root.
        try:
            rel = os.path.relpath(args.out.resolve(), page.resolve().parent)
        except ValueError:
            rel = str(args.out)
        rel = rel.replace(os.sep, "/")
        want = {f"{stem}.svg": _svg_for_kwargs(kw) + "\n" for stem, kw in gallery_specs()}
        md = gallery_markdown(rel)
        if args.check:
            stale = [n for n, svg in want.items()
                     if not (dest / n).is_file() or (dest / n).read_text(encoding="utf-8") != svg]
            page_stale = not page.is_file() or page.read_text(encoding="utf-8") != md
            if stale or page_stale:
                what = []
                if stale:
                    what.append(f"{len(stale)} gallery badge(s) out of date "
                                f"({', '.join(sorted(stale)[:6])})")
                if page_stale:
                    what.append(f"{page.name} is out of date")
                print(f"::error::{'; '.join(what)}. Run 'make gallery'.", file=sys.stderr)
                return 1
            print(f"Gallery check passed - {len(want)} badge(s) and {page.name} are current.")
            return 0
        dest.mkdir(parents=True, exist_ok=True)
        for name, svg in want.items():
            f = dest / name
            if not f.is_file() or f.read_text(encoding="utf-8") != svg:
                f.write_text(svg, encoding="utf-8")
        # Prune a gallery badge whose icon or token no longer exists, so the
        # page can never reference a glyph the registry dropped.
        for f in sorted(dest.glob(f"{GALLERY_PREFIX}*.svg")):
            if f.name not in want:
                f.unlink()
                print(f"Pruned {f.name} (no longer in the registry).")
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(md, encoding="utf-8")
        print(f"Rendered {len(want)} gallery badge(s) and wrote "
              f"{page.relative_to(root) if page.is_relative_to(root) else page}.")
        return 0

    if args.icons:
        print("\n".join(sorted(ICONS)))
        return 0
    if args.palette:
        for tok, hexc in PALETTE.items():
            print(f"{tok:8} {hexc}")
        return 0
    if args.self_test:
        return self_test()

    if args.theme and args.theme != RAINBOW and args.theme not in PRINTS:
        print(f"::error::--theme: unknown print {args.theme!r} "
              f"(one of {', '.join(PRINTS)}, or {RAINBOW})", file=sys.stderr)
        return 1

    if not args.data.exists():
        if args.check:
            print(f"::notice::no {args.data.name}; badge kit not in use, skipping check.")
            return 0
        print(f"::error::badge data file not found: {args.data}", file=sys.stderr)
        return 1

    if args.set:
        updates: dict[str, tuple[str, str | None]] = {}
        for spec in args.set:
            if "=" not in spec:
                print(f"::error::--set expects NAME=MESSAGE[:COLOR], got {spec!r}",
                      file=sys.stderr)
                return 1
            name, _, value = spec.partition("=")
            message, color = value, None
            if ":" in value:
                head, _, tail = value.rpartition(":")
                # Only treat the suffix as a color when it actually is one,
                # so a message containing ':' passes through untouched.
                if tail in PALETTE or _HEX_COLOR.match(tail):
                    message, color = head, tail
            updates[name.strip()] = (message, color)
        missing = set_values(args.data, updates)
        if missing:
            print(f"::error::--set: no entry named {', '.join(missing)} in "
                  f"{args.data.name}", file=sys.stderr)
            return 1
        print(f"Updated {len(updates)} value(s) in {args.data.name}.")

    if args.randomize_static is not None:
        changed = randomize_static(args.data, args.randomize_static)
        if changed:
            print(f"Rotated {len(changed)} static badge color(s) (seed "
                  f"{args.randomize_static!r}): "
                  + ", ".join(f"{n}->{c}" for n, c in changed) + ".")
        else:
            print(f"Static badge colors already current for seed "
                  f"{args.randomize_static!r} - no change.")

    badges = load_badges(args.data)
    if not badges:
        print(f"::warning::no badges defined in {args.data}")
        return 0
    errors = validate(badges)
    if errors:
        for e in errors:
            print(f"::error::{args.data.name}: {e}", file=sys.stderr)
        return 1

    if args.markdown:
        # Paths are relative to the repository root, which is where a README
        # resolves them; an output tree outside the repository is printed as
        # given, since no relative form of it exists.
        try:
            rel = args.out.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = args.out.as_posix()
        for b in badges:
            label, message = str(b.get("label", "")), str(b.get("message", ""))
            alt = f"{label}: {message}" if label and message else (label or message)
            link = str(b.get("link") or "")
            paths = paths_for(b)
            if len(paths) == 2:
                # A static plate's pair: the night file for a dark theme.
                pic = (f'<picture><source media="(prefers-color-scheme: dark)" '
                       f'srcset="{rel}/{paths[1]}"><img alt="{escape(alt)}" '
                       f'src="{rel}/{paths[0]}"></picture>')
                print(f'<a href="{escape(link)}">{pic}</a>' if link else pic)
                continue
            img = f"![{alt}]({rel}/{paths[0]})"
            print(f"[{img}]({link})" if link else img)
        return 0

    # Each badge lands in a TYPE subfolder under assets/badges/: dynamic/ for
    # the automation-refreshed health badges (gold label), static/ for every
    # fixed-value badge. The doc-header classification library shares static/
    # but is owned by scripts/localize-badges.py, so reserve its files - this
    # generator's orphan check and pruning must never touch them.
    # A static blueprint plate is two of these, its day and night files.
    expected: dict[str, str] = {}
    rainbow = rainbow_shade(root)
    for b in badges:
        try:
            expected.update(files_for(b, rainbow, args.theme))
        except BadgeError as e:
            print(f"::error::{args.data.name}: {b['name']}: {e}", file=sys.stderr)
            return 1
    # The gallery shares static/ but is not in the data file, so reserve it
    # the same way the codemod's classification badges are reserved.
    reserved = (_reserved_doc_badges(root, args.data, args.out)
                | {f"static/{n}" for n in gallery_filenames()})
    on_disk: dict[str, Path] = {}
    for sub in ("static", "dynamic"):
        d = args.out / sub
        if d.is_dir():
            for p in sorted(d.glob("*.svg")):
                on_disk[f"{sub}/{p.name}"] = p
    orphans = sorted(set(on_disk) - set(expected) - reserved)

    if args.check:
        stale, regen = [], []
        for rel, svg in expected.items():
            dest = args.out / rel
            current = dest.read_text(encoding="utf-8") if dest.exists() else ""
            if current == svg:
                continue
            m = _STAMP.search(current)
            if current and m and m.group(1) != KIT_VERSION:
                # Rendered by another kit version (engine sync brought a new
                # renderer). Not an error: the next `make badges` or the daily
                # Badge Refresh run regenerates it through the PR flow.
                regen.append(rel[:-len(".svg")])
            else:
                stale.append(rel[:-len(".svg")])
        for rel in orphans:
            stale.append(f"{rel} (orphaned - not in {args.data.name})")
        if stale:
            print(f"::error::{len(stale)} badge SVG(s) out of date: "
                  f"{', '.join(stale)}. Run 'make badges'.", file=sys.stderr)
            return 1
        if regen:
            print(f"::notice::{len(regen)} badge(s) rendered by another kit "
                  f"version ({', '.join(regen)}); the next 'make badges' run "
                  f"re-stamps them.")
        print(f"Badge check passed - {len(expected)} committed SVG(s) match "
              f"{args.data.name}.")
        return 0

    for rel, svg in expected.items():
        dest = args.out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(svg, encoding="utf-8")
    for rel in orphans:
        # Each type folder mirrors the data file (minus the reserved doc
        # library) - a file no entry names anymore is generator output whose
        # entry was removed.
        (args.out / rel).unlink()
        print(f"Pruned orphaned {rel} (no entry in {args.data.name}).")
    print(f"Rendered {len(badges)} badge(s) as {len(expected)} SVG(s) into "
          f"{args.out}/{{static,dynamic}} from {args.data.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
