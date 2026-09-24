<!--
title: '🏷️ BADGE KIT'
description: 'The specification for the self-hosted badge generator, from palette tokens to the data-file schema.'
tags: [badges, interface, automation, specification]
category: docs
-->

<!-- markdownlint-disable MD041 -->

<div align="center">

# 🏷️ BADGE KIT

<a name="top"></a>

**Badges a repository draws for itself: committed SVGs from one generator, never a third-party request.**

_Drawn, never fetched._

[![Status: Active](../assets/badges/static/status.svg)](../)
[![Role: Tool](../assets/badges/static/role.svg)](../)
[![Context: Badges](../assets/badges/static/context.svg)](../)
[![License: MIT](../assets/badges/static/license.svg)](../LICENSE)

</div>

---

## 🎯 Intent

A badge here is a **committed SVG**, rendered by a generator from a small data
file. That removes a third-party dependency from every README render, removes
any rate-limit risk, and puts the palette, the icons, and the geometry fully
under your control.

The kit is two programs that share one output tree:

| Part                      | Job                                                                   |
| :------------------------ | :-------------------------------------------------------------------- |
| `src/badge-kit.py`        | The renderer. Turns a data file into committed SVGs.                  |
| `src/localize-badges.py`  | The codemod. Rewrites `img.shields.io` hotlinks in Markdown into one. |

Both are stdlib-only Python. PyYAML is used when it is installed and a
built-in reader substitutes when it is not, so the kit runs on a bare
`python3` with nothing to install.

### 🗂️ Folder layout

Committed badges live in exactly two **type** folders, and nothing decides
which one a badge lands in except its label color:

- **`dynamic/`**: badges whose value changes over time (`build`,
  `last-commit`, a score). **Gold label.**
- **`static/`**: every fixed-value badge: identity, classification, calls to
  action, posture. **Black label.**

---

## 🧱 Anatomy

A badge is two solid segments with an optional icon left of the label, in one
of three interchangeable styles:

| Style           | Job                | Look                                                               |
| :-------------- | :----------------- | :----------------------------------------------------------------- |
| `for-the-badge` | **Headline**       | **Default.** 28px tall, bold uppercase, letter-spaced.             |
| `flat`          | **Standard**       | 20px tall, rounded corners, subtle gradient sheen, natural case.   |
| `flat-square`   | Standard           | The `flat` geometry with square corners and no gradient.           |
| `plastic`       | Standard           | 18px, softly rounded, with a bevel gradient. The shields.io shape. |
| `pill`          | Standard           | 20px with fully rounded ends and wider padding.                    |
| `compact`       | **Dense**          | 16px with a 9px face, for dense rows and inline use.               |

Grouped by the job, not by the order they were added: **headline** styles are
bold uppercase for a masthead or a document header, **standard** styles are
natural-case chips for a body row, and **dense** is shorter than a line of
text. [The gallery draws all six](Gallery.md).

Geometry is data, not code: a style is a corner radius, an optional overlay
gradient, and a scale applied to the 11px metric tables. Advance widths are
linear in font size, so a style at another size measures exactly rather than
approximately.

- **Label** (left): the category. Black for static, metallic gold for
  dynamic-health.
- **Message** (right): the value. Its color carries the semantic meaning.
- **Icon**: an in-house glyph, stroked in the label's ink color so it reads on
  any background.

Text is measured with **real Verdana metrics** (the MIT-licensed `anafanafo`
tables shields.io itself uses) and pinned with SVG `textLength`, so a badge
renders at exactly the computed width on every platform. A viewer without
Verdana sees the same geometry. Ink color is chosen by relative luminance, so
white text lands on the gold label and dark text on the license yellow.

Badges are solid chips, so they render identically in light and dark themes.

---

## 🗂️ The Data File

Each entry in `.github/badges.yml` describes one badge:

| Field           | Required | Meaning                                                                     |
| :-------------- | :------: | :-------------------------------------------------------------------------- |
| `name`          |   yes    | Output basename (kebab-case, unique). Decides the filename.                 |
| `label`         |  yes\*   | Left segment text. \*At least one of `label`/`message` must be non-empty.   |
| `message`       |  yes\*   | Right segment text.                                                         |
| `label_color`   |    no    | Palette token or `#RRGGBB`. Static: `black`. Dynamic-health: `gold`.        |
| `message_color` |    no    | Palette token or `#RRGGBB`, carrying the semantic meaning.                  |
| `icon`          |    no    | A key from the icon registry. Omit for no icon.                             |
| `style`         |    no    | `for-the-badge` (default), `flat`, or `flat-square`.                        |
| `link`          |    no    | Where the badge points when embedded (reference only).                      |

Every field is **validated**. An unknown icon, color token, style, duplicate
or non-kebab-case name fails the render with a precise error rather than
silently producing a wrong badge.

`label_color` also decides the folder. The gold label routes a badge to
`dynamic/`, whether it is written as the token `gold` or as its hex
`#C0A062`; validation and routing resolve the color the same way, so a badge
can never pass the health rule and then land in the wrong folder.

See [`badges.example.yml`](badges.example.yml) for a starter file.

---

## 🎨 Palette

64 named tokens, one per icon, tuned to one saturation/lightness family so any
two sit together without clashing. Each was checked against every other and
clears the palette's own minimum spacing, so no two read as the same color. A raw `#RRGGBB` works anywhere a token does, so the
space of badges stays unbounded. The generator is the source of truth:

```bash
python3 src/badge-kit.py --palette
```

**[The gallery draws all 40](Gallery.md)**, each painted in its own token with
its hex beside it, so you pick one by looking rather than by imagining it.

**Role anchors** carry the color roles: `black` (static label), `gold`
(dynamic-health label), `green` (success), `pink` (roles), `purple` (context),
`yellow` (license), `red` (critical), `blue` (navigation), `violet`, `olive`,
`slate`, `teal`, `orange`.

**The other 50** run from red through to the neutrals, grouped by hue in the gallery:

`salmon`, `coral`, `brick`, `crimson`, `maroon`, `cherry`, `clay`, `peach`, `tangerine`, `brown`, `apricot`, `tan`, `honey`, `amber`, `sand`, `ivory`, `mustard`, `moss`, `lime`, `sage`, `forest`, `emerald`, `jade`, `mint`, `turquoise`, `aqua`, `cyan`, `ocean`, `sky`, `steel`, `azure`, `denim`, `cobalt`, `navy`, `indigo`, `iris`, `lavender`, `amethyst`, `plum`, `mauve`, `orchid`, `fuchsia`, `magenta`, `ruby`, `rose`, `charcoal`, `taupe`, `gray`, `stone`, `ash`

### The traffic-light rule

A **dynamic-health** badge (gold label) uses color to signal a **status**, so
its message color is restricted to `green` (healthy), `yellow` (degraded) and
`red` (failing), plus `slate` for an explicit "no status yet". An arbitrary
hue on a gold label is a mechanical error, not a style note. Validation
rejects it. Static badges are unconstrained.

### Weekly color rotation

Decorative static badges can rotate their message color so a header feels
alive instead of sitting on one fixed hue:

```bash
python3 src/badge-kit.py --randomize-static "$(date -u +%GW%V)"
```

The seed is the ISO year and week, so the pick is deterministic within a week
(a mid-week re-run is a clean no-op) and changes every Monday. Badges already
painted a **reserved** color are left fixed: the traffic-light triad is
treated as semantic, as are the `pink` and `purple` identity slots, and
gold-label badges are never touched. That leaves 31 colors to draw from,
keyed per badge so they vary across a row.

---

## 🖋️ Icon Registry

64 line glyphs on a 24×24 grid, drawn in-house so the kit never pulls a logo
from a third-party icon service. **[The gallery draws every one](Gallery.md)**
with its name on it. To list them as text:

```bash
python3 src/badge-kit.py --icons
```

Add one by dropping a new 24×24 stroke path into the `ICONS` registry. The
self-test renders every registered glyph, so a malformed path cannot land.

---

## 🚀 Rendering

```bash
make badges     # localize, then render
make render     # render only
make check      # CI gate
```

Rendering **prunes**: any SVG in the output directory that no entry names
anymore is deleted, so the folder always mirrors the data file exactly. Output
is deterministic, so re-running produces no spurious diff.

Every SVG carries a **kit version stamp**. `--check` hard-fails only
*same-version* drift, and treats a version difference as "regenerate on the
next render", so upgrading the kit can never wedge a downstream CI run. The
self-test additionally pins one canonical render to a `GOLDEN_SHA`, so
rendered output cannot change without someone bumping the version knowingly.

### 🧰 Command line

Both programs take the same three location flags, so a run can be pointed at
any repository and any badge tree. Each defaults under `--root`, which itself
defaults to `GITHUB_WORKSPACE` and then the working directory:

| Flag     | Default               | Meaning                                              |
| :------- | :-------------------- | :--------------------------------------------------- |
| `--root` | workspace, else `cwd` | The repository being rendered for.                   |
| `--data` | `.github/badges.yml`  | The badge data file.                                 |
| `--out`  | `assets/badges`       | The badge tree (`static/` and `dynamic/` under it).  |

`badge-kit.py` adds:

| Flag                        | Effect                                                              |
| :-------------------------- | :------------------------------------------------------------------ |
| `--check`                   | Verify committed SVGs match the data file. Writes nothing.          |
| `--set NAME=MESSAGE[:COLOR]`| Update one value in place, then render. Repeatable.                 |
| `--randomize-static SEED`   | Rotate decorative static colors, keyed by `SEED`, then render.      |
| `--markdown`                | Print one ready-to-paste embed line per badge. Writes nothing.      |
| `--icons`, `--palette`      | List the registries.                                                |
| `--self-test`               | Renderer and parser invariants, no repository needed.               |
| `--version`                 | The kit version stamped into every SVG.                             |

`--markdown` is how the `link` field earns its keep. Each line carries the
badge's alt text (label and message, original casing), its path relative to
`--root`, and its link when it has one:

```markdown
[![Build Status: Passing](assets/badges/dynamic/build.svg)](./actions)
```

`localize-badges.py` adds `--check`: no shields.io hotlink remains, no
relative doc-badge reference outside the root README, and every referenced
doc badge exists and is current.

---

## 📡 Dynamic Values

Dynamic-health badges carry measured values, refreshed by automation rather
than hotlinked:

```bash
python3 src/badge-kit.py --set build=Failing:red
```

`--set NAME=MESSAGE[:COLOR]` updates one badge's value in the data file
**preserving the file's comments and layout**, then re-renders. A `:suffix` is
treated as a color only when it actually is one, so a message containing a
colon passes through unchanged.

---

## 🔗 Embedding

Reference the committed SVG, always with descriptive alt text:

```markdown
![Build status of the main CI pipeline](assets/badges/dynamic/build.svg)
```

**Relative or absolute?** GitHub only rewrites relative image paths in the
main blob and README views. The pull-request rich diff, the security-policy
tab, and client-side navigation leave them unresolved, so a relative badge
renders broken exactly where community-health files are most often read.

- **Root `README.md`** renders where relative paths resolve, so relative is fine.
- **Everywhere else**, prefer the absolute raw URL pinned to the default
  branch. `localize-badges.py` writes that form automatically.

One caveat: on a **private** repository GitHub's image proxy cannot fetch raw
content, so badges render only in the authenticated blob views there. This
clears the moment the repository is public.

> [!NOTE]
> A freshly pushed badge does not render instantly. `raw.githubusercontent.com`
> has to resolve the new blob at the edge, and GitHub's image proxy has to
> fetch and cache it once. Until both settle the badge shows broken, and its
> raw URL can return a 404 that was cached before the blob existed. That is
> propagation, not a wrong link, and it clears on its own.

**Ordering:** never mix the two kinds in one row. Static badges come first;
the dynamic-health row sits below them, separated by a blank line.

---

<div align="center">

**Self-drawn. Self-hosted. Never rate-limited.**

[↑ Back to Top](#top)

</div>
