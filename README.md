<!--
title: '🏷️ BADGES'
description: 'Badges a repository draws for itself, rendered as committed SVGs from one data file so no README depends on a third-party service.'
tags: [badges, svg, markdown, github-actions]
category: docs
-->

<!-- markdownlint-disable MD041 -->

<div align="center">

# 🏷️ BADGES

<a name="top"></a>

**Badges a repository draws for itself.**

_Drawn, never fetched._

[![Status: Active](assets/badges/static/status.svg)](./)
[![Role: Action](assets/badges/static/role.svg)](./)
[![Context: Badges](assets/badges/static/context.svg)](./)
[![License: MIT](assets/badges/static/license.svg)](./LICENSE)

[![Dependencies: None](assets/badges/static/dependencies.svg)](./)
[![Palette: 64 tokens](assets/badges/static/palette.svg)](./)
[![Icons: 64 glyphs](assets/badges/static/icons.svg)](./)
[![Use this action](assets/badges/static/use-action.svg)](#-use-it-in-your-own-repository)

</div>

---

## 💡 What This Is

A badge served from `img.shields.io` is a third-party request on every page
view, and a dependency on somebody else's uptime for your README to render.
This draws them instead.

A badge here is a **committed SVG**, rendered from a small data file you own.
No request at render time, nothing to rate-limit, and the palette, icons and
geometry are yours.

It is two programs sharing one output tree:

| Part                     | Job                                                                 |
| :----------------------- | :------------------------------------------------------------------ |
| `src/badge-kit.py`       | **The renderer.** A data file becomes committed SVGs.               |
| `src/localize-badges.py` | **The codemod.** `img.shields.io` hotlinks in Markdown become one.  |

Both are **stdlib-only Python**. PyYAML is used when it happens to be
installed and a built-in reader substitutes when it is not, so this runs on a
bare `python3` with nothing to install and nothing to cache.

**Called, never copied.** Your repository holds a data file and a stub that
pins `uses: tannergolden/badges@v1`. The drawing happens here, so a fix to a
glyph or a color lands once and reaches every badge pinned to `v1`. That is
how [`tannergolden/banners`](https://github.com/tannergolden/banners) draws
the two ends of a page and its body, how
[`tannergolden/trophies`](https://github.com/tannergolden/trophies) draws a
case, and how [`tannergolden/standards`](https://github.com/tannergolden/standards)
delivers automation; this draws the badges, in the same palette, under the
same rule. [`tannergolden/markdown`](https://github.com/tannergolden/markdown)
calls all three kits from one stub.

---

## 🟢 Up 24/7/365

Most badge services are a **live request on every page view**. Your README
renders only while their servers answer, so their outages, slow days and rate
limits land on your page as broken images, and nothing on your side can fix
it. It is a dependency you cannot see until the moment it fails.

A badge here has **no server to be down**. It is a committed SVG, served by
GitHub with the rest of your repository, so it is up exactly as long as your
repository is: every hour of every day, all year round, with no third party
in the path. There is no endpoint to fail, no quota to exhaust and no status
page to check. If someone can see your README, they can see your badges. That
is not an uptime promise to take on trust; it is a property of a committed
file.

|                  | Hosted badge service                    | Badges drawn here                    |
| :--------------- | :-------------------------------------- | :----------------------------------- |
| **A badge is**   | An HTTP response, answered at view time | A file in your repository            |
| **Down when**    | Their service is                        | Never on its own, only with the page |
| **Slow when**    | Their service is busy                   | Never, it is a static file           |
| **Rate limits**  | Yes, and not yours to raise             | None                                 |
| **Changes when** | Their side deploys                      | You commit                           |

---

## 🖼️ What It Looks Like

Six lines of YAML in, one committed SVG out:

```yaml
- name: tests
  label: Tests
  message: 1,204 Passing
  message_color: emerald
  icon: flask
```

![Tests: 1,204 passing](assets/badges/static/hue-emerald.svg)

Every badge below this line is a real file in this repository, rendered by the
kit from [`.github/badges.yml`](.github/badges.yml) into `assets/badges/`.
Nothing on this page is fetched from anywhere.

### Six styles, grouped by the job

`for-the-badge` is the default and the **headline** style: bold uppercase, for
a masthead or a document header.

![The for-the-badge style](assets/badges/static/gallery-style-for-the-badge.svg)

**Standard** styles are natural-case chips for a body row, the same shape
square, rounded, bevelled or fully round:

![The flat style](assets/badges/static/gallery-style-flat.svg)
![The flat-square style](assets/badges/static/gallery-style-flat-square.svg)
![The plastic style](assets/badges/static/gallery-style-plastic.svg)
![The pill style](assets/badges/static/gallery-style-pill.svg)

**Dense** is shorter than a line of text, for a table of many badges or one
sitting inline in a sentence:

![The compact style](assets/badges/static/gallery-style-compact.svg)

### Health badges follow a traffic light

A **gold label** means the value changes over time, so its color has to mean
something. The message is restricted to green, yellow and red, plus slate for
an explicit "no status yet". Any other hue on a gold label is rejected at
render time rather than quietly drawn.

![Build: passing](assets/badges/dynamic/health-passing.svg)
![Coverage: 78 percent](assets/badges/dynamic/health-degraded.svg)
![Deploy: failing](assets/badges/dynamic/health-failing.svg)
![Scan: no data](assets/badges/dynamic/health-unknown.svg)

### Static badges can use the whole palette

64 tokens, one per icon, tuned to one saturation and lightness family so any
two sit together without clashing. Every one was checked against every other
and clears the palette's own minimum spacing, so no two read as the same
color. A raw `#RRGGBB` works anywhere a token does.

![Release: v2.4.0](assets/badges/static/hue-crimson.svg)
![Docs: live](assets/badges/static/hue-azure.svg)
![Design: system](assets/badges/static/hue-fuchsia.svg)
![Bundle: 42 kB](assets/badges/static/hue-amber.svg)

![Latency: 38 ms](assets/badges/static/hue-teal.svg)
![Runtime: Python 3.12](assets/badges/static/hue-plum.svg)
![Issues: 3 open](assets/badges/static/hue-coral.svg)
![Uptime: 99.98 percent](assets/badges/static/hue-forest.svg)
![Platform: Linux](assets/badges/static/hue-steel.svg)

### 64 icons, drawn in-house

Line glyphs on a 24x24 grid, stroked in the label's ink color so they read on
any background. No logo is ever pulled from an icon CDN. These six are a
sample: **[every icon and every color token is in the gallery](docs/Gallery.md)**,
generated from the registries so it cannot drift.

![Security: hardened](assets/badges/static/icon-lock.svg)
![Community: welcome](assets/badges/static/icon-users.svg)
![Deploy: automated](assets/badges/static/icon-rocket.svg)
![Storage: Postgres](assets/badges/static/icon-database.svg)
![CDN: global](assets/badges/static/icon-globe.svg)
![Rank: top 10](assets/badges/static/icon-trophy.svg)

### Blueprint plates, drawn like the banners

Every style has a **blueprint twin**, drawn the way
[`tannergolden/banners`](https://github.com/tannergolden/banners) draws a
header: the label lettered on drafting paper, the value on a solid block of
the print, and the plate framed in the print's line. Name the twin in `style:`.
It keeps its base style's height, corner, padding and case, so swapping one for
the other never moves a row.

```yaml
- name: plate-tests
  label: Tests
  message: 1,204 Passing
  icon: flask
  style: blueprint-for-the-badge
  print: greenprint
```

<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/plate-tests-dark.svg"><img alt="Tests: 1,204 Passing" src="assets/badges/static/plate-tests.svg"></picture>

A static plate is drawn in a **print** rather than a message color, and a
print has a day and a night: its lines on white paper, and the sheet those
lines are printed on. So a static plate is **two files**, `plate-tests.svg`
and `plate-tests-dark.svg`, and GitHub shows the one that matches the
reader's theme. Switch yours to see the other. `snippets` prints the
`<picture>` that embeds the pair. There are eleven prints, the same eleven the
banners draw in, with `blueprint` the default; a few of them are below, and
[the gallery draws all eleven](docs/Gallery.md#️-prints). A plate whose print
is `rainbowprint` is drawn in the colour the page's banners are in now: the
banners' lock records which colour of the spectrum their last update took,
and the plate follows it, so a row of plates changes colour with the header
above it. Without banners it is the redprint, the first of the spectrum.

<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/plate-release-dark.svg"><img alt="Release: v2.4.0" src="assets/badges/static/plate-release.svg"></picture>
<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/plate-bundle-dark.svg"><img alt="Bundle: 42 kB" src="assets/badges/static/plate-bundle.svg"></picture>
<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/plate-docs-dark.svg"><img alt="Docs: Live" src="assets/badges/static/plate-docs.svg"></picture>

<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/plate-runtime-dark.svg"><img alt="Runtime: Python 3.12" src="assets/badges/static/plate-runtime.svg"></picture>
<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/plate-platform-dark.svg"><img alt="Platform: Linux" src="assets/badges/static/plate-platform.svg"></picture>

A **live** plate is a gold label, the same rule as a health badge, and the gold
sheet tells it apart from a static plate before a word is read. Its value is
drawn in the print its state names: green in the greenprint, red in the
redprint, slate in the blackprint, and yellow in the orangeprint, because a
mustard block would disappear into the gold beside it. One file serves both
themes. `reserve` sizes the value block for every value it lists, so a build
that flips from Passing to Failing never changes width:

```yaml
- name: plate-build
  label: Build
  message: Passing
  label_color: gold
  message_color: green
  icon: check
  style: blueprint-for-the-badge
  reserve: Failing
```

![Build: Passing](assets/badges/dynamic/plate-build.svg)
![Coverage: 78 percent](assets/badges/dynamic/plate-coverage.svg)
![Deploy: Failing](assets/badges/dynamic/plate-deploy.svg)
![Scan: No Data](assets/badges/dynamic/plate-scan.svg)

All six twins, each beside its live plate:

<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/gallery-blueprint-for-the-badge-dark.svg"><img alt="The blueprint-for-the-badge style" src="assets/badges/static/gallery-blueprint-for-the-badge.svg"></picture>
![The blueprint-for-the-badge style, live](assets/badges/static/gallery-blueprint-for-the-badge-live.svg)

<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/gallery-blueprint-flat-dark.svg"><img alt="The blueprint-flat style" src="assets/badges/static/gallery-blueprint-flat.svg"></picture>
![The blueprint-flat style, live](assets/badges/static/gallery-blueprint-flat-live.svg)
<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/gallery-blueprint-flat-square-dark.svg"><img alt="The blueprint-flat-square style" src="assets/badges/static/gallery-blueprint-flat-square.svg"></picture>
![The blueprint-flat-square style, live](assets/badges/static/gallery-blueprint-flat-square-live.svg)

<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/gallery-blueprint-plastic-dark.svg"><img alt="The blueprint-plastic style" src="assets/badges/static/gallery-blueprint-plastic.svg"></picture>
![The blueprint-plastic style, live](assets/badges/static/gallery-blueprint-plastic-live.svg)
<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/gallery-blueprint-pill-dark.svg"><img alt="The blueprint-pill style" src="assets/badges/static/gallery-blueprint-pill.svg"></picture>
![The blueprint-pill style, live](assets/badges/static/gallery-blueprint-pill-live.svg)

<picture><source media="(prefers-color-scheme: dark)" srcset="assets/badges/static/gallery-blueprint-compact-dark.svg"><img alt="The blueprint-compact style" src="assets/badges/static/gallery-blueprint-compact.svg"></picture>
![The blueprint-compact style, live](assets/badges/static/gallery-blueprint-compact-live.svg)

The lettering is **outlined Barlow Condensed**, the banners' face: every glyph
is a path rather than text in a font, so a plate looks the same on every
device, whatever fonts it has. A label with a character the outlines lack
(they cover Latin-1 and Latin Extended-A) is refused at render time rather
than drawn with a gap in it.

---

## 🚀 Use It In Your Own Repository

Add `.github/badges.yml` (start from [`docs/badges.example.yml`](docs/badges.example.yml)),
then pin a stub to the `v1` tag. That stub is the whole interface: nothing is
copied into your repository and there is no generator for you to keep current,
so a fix here reaches you the moment it is published.

The action renders into **your** checkout, never its own, so the committed SVGs
land beside your data file exactly where you asked for them.

One stub per kit, or one for the whole page:
[`tannergolden/markdown`](https://github.com/tannergolden/markdown) calls this
kit, the banners and the trophies from a single workflow, each at its own
hour, so a README that wants all three needs one stub rather than three.

### Render on every push, and commit what changed

`commit: true` stages what the run changed, commits it, and pushes to the
branch that was checked out. The job needs `contents: write` and nothing
else: no git steps of its own, no identity to configure.

```yaml
name: Badges
on: [push]

permissions:
  contents: write

jobs:
  badges:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: tannergolden/badges@v1
        with:
          mode: render
          commit: true
```

That commit is **authored by Tanner Golden**, the kit's author, and
committed by the workflow that ran it, `github-actions[bot]`. What changed
is the kit's output rather than anything your workflow wrote, so the author
field says who drew the badges and the committer field says what pushed
them, the way a dependency update carries its bot's name. The subject is
`chore(badges): 🏷️ re-render badges` unless `commit-message` says
otherwise, and the body records the mode, the data file, and a link to the
run that made it. Only what the run changed is staged, so a checkout that
was already carrying edits keeps them.

Rather commit yourself, under an identity of your own? Leave `commit` off:
the `changed` output still says whether there is anything to commit.

<details>
<summary>Committing yourself, from the changed output</summary>

```yaml
      - uses: tannergolden/badges@v1
        id: badges
        with:
          mode: render
      - if: steps.badges.outputs.changed == 'true'
        run: |
          git config user.name  'github-actions[bot]'
          git config user.email 'github-actions[bot]@users.noreply.github.com'
          git add assets/badges
          git commit -m 'chore(badges): re-render'
          git push
```

</details>

### Or gate on it, so a stale badge fails the build

Nothing to commit and nothing to push. The job simply fails if the committed
SVGs no longer match the data file.

```yaml
- uses: actions/checkout@v5
- uses: tannergolden/badges@v1
  with:
    mode: check
```

### Refresh live values on a schedule

`set` writes measured values into the data file before rendering, preserving
its comments and layout. `randomize-seed` rotates the decorative colors, keyed
by the ISO week, so the pick is stable within a week and changes every Monday.
With `commit: true`, the refreshed values land on the branch by themselves.

```yaml
on:
  schedule:
    - cron: '0 13 * * *'
jobs:
  refresh:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v5
      - id: measure
        run: echo "commit=$(git log -1 --format=%cr)" >> "$GITHUB_OUTPUT"
      - uses: tannergolden/badges@v1
        with:
          mode: render
          set: |
            build=Passing:green
            last-commit=${{ steps.measure.outputs.commit }}:green
          randomize-seed: ${{ github.run_id }}
          commit: true
```

### Migrate a README that already uses shields.io

`localize` finds every `img.shields.io` hotlink in your tracked Markdown,
renders each one as a committed SVG, and rewrites the reference to point at
it. Identical badges collapse onto **one** file: forty documents carrying the
same `Status: Active` badge get one SVG between them, not forty.

```yaml
- uses: tannergolden/badges@v1
  with:
    mode: localize
```

### Get the lines to paste

`snippets` prints one ready-to-paste Markdown line per badge, alt text and
link included, to the log and to the job summary. Nothing is written to the
repository.

```yaml
- uses: actions/checkout@v5
- uses: tannergolden/badges@v1
  with:
    mode: snippets
```

### Action inputs

| Input            | Default              | Meaning                                                                  |
| :--------------- | :------------------- | :----------------------------------------------------------------------- |
| `mode`           | `render`             | `render`, `check`, `localize`, `all`, or `snippets`.                     |
| `data`           | `.github/badges.yml` | Badge data file, relative to the repository root.                        |
| `out`            | `assets/badges`      | Output directory for the committed SVGs.                                 |
| `set`            | none                 | Newline-separated `NAME=MESSAGE[:COLOR]` updates applied first.          |
| `randomize-seed` | none                 | Rotate decorative colors, keyed by this seed.                            |
| `commit`         | `false`              | `true` commits what the run changed, as the kit's author, and pushes it. |
| `commit-message` | per mode             | Subject of that commit. The body is written for you.                     |

Two outputs: `changed` is `'true'` when the run modified a tracked file, and
`commit` is the SHA the run pushed, or empty when it made no commit.

---

## ⚙️ The Data File

```yaml
badges:
  - name: status
    label: Status
    message: Active
    label_color: black
    message_color: green
    icon: pulse
    link: ./
```

`name` decides the filename. `label_color` decides the folder: a **gold**
label is a dynamic-health badge and lands in `assets/badges/dynamic/`,
everything else is static and lands in `assets/badges/static/`.

A blueprint style adds two fields. `print` is a static plate's colour
(`blueprint` unless you name another), and `reserve` lists the other values a
plate is sized for, `Passing, Failing`. A static plate takes no
`message_color` and writes `<name>.svg` and `<name>-dark.svg`; a live plate
takes no `print`.

Every field is validated. An unknown icon, color token, style, print,
duplicate or non-kebab-case name fails the render with a precise error rather
than quietly drawing the wrong badge, and so does a field a badge would
ignore, like a message color on a plate drawn in its print.

---

## 🎨 What You Get To Draw With

Text is measured with **real Verdana metrics**, the MIT-licensed `anafanafo`
tables shields.io itself uses, and pinned with SVG `textLength`. A badge
renders at the same width on every platform, including viewers with no Verdana
installed. These badges are solid chips, so they look identical in light and
dark themes. A blueprint plate is lettered in outlines instead, and a static
one brings its own night file.

**[`docs/Gallery.md`](docs/Gallery.md) draws all of them**: 64 icons grouped by
what they are for, 64 color tokens grouped by hue with their hex, the
6 styles and the health colors, then every blueprint twin in all 11 prints,
each rendered as a real badge with its own name on it, so you pick by eye and copy the name. It is generated from the
registries by `make gallery` and verified by `make check`, so it can never fall
behind what the kit can actually draw.

### 1,574,040 badges, before you write a word

Multiply the registries out and they express **1,574,040 visually distinct
badges**:

```text
4,036 colour pairs  x  65 icons  x  6 styles
```

The colour figure is not 64 x 64. The traffic-light rule refuses 60 of those
4,096 pairs, because a gold label may only paint its message green, yellow,
red or slate. That refusal is the whole point of the rule:

| Kind | Combinations |
| :--- | ---: |
| Static, any non-gold label | 1,572,480 |
| Health, gold label | 1,560 |

Health badges are **0.1%** of the space. A status signal has almost no room to
be creative in, which is exactly why green always means the same thing
everywhere it appears.

Label and message are free text, so the real number is unbounded; the figure
above is everything except the wording. It is counted rather than claimed:
`combination_count()` filters every colour pair through the same `validate()`
the renderer uses, and a test fails if this README disagrees with it.

The blueprint plates are a second space beside that one, since a plate takes a
print or a state rather than a colour pair: **5,850 more**, of which 4,290 are
static (11 prints x 65 icons x 6 styles) and 1,560 live (4 states x 65 icons x
6 styles).

---

## 🔁 How It Runs

**Every render is deterministic and prunes.** The same data file produces
byte-identical SVGs, so re-running makes no spurious diff, and a file that no
entry names anymore is deleted, so the output folder always mirrors the data.

**Every SVG carries a kit version stamp.** `--check` hard-fails only
same-version drift and treats a version difference as "regenerate next time",
so upgrading the kit can never wedge a consumer's CI. The self-test pins one
canonical render to a golden hash, and a plate's day, night and live files to
another, so rendered output cannot change unless someone bumps the version
knowingly.

**Every commit is a Conventional Commit.** With `commit: true` the run
commits what it drew as `chore(badges): 🏷️ re-render badges`, authored by the
kit's author and committed by `github-actions[bot]`, with a body recording
the mode, the data file and a link to the run, per the
[commit standard](https://github.com/tannergolden/standards/blob/Development/docs/distribution/Conventional-Commits.md).
Only what the run changed is staged.

---

## 🧭 Layout

The files a consumer resolves at the tag, and where everything else lives:

<details>
<summary>Every file, and what it is for</summary>

```bash
badges/
├── action.yml                 the composite action
├── src/
│   ├── badge-kit.py           the renderer
│   ├── localize-badges.py     the Markdown codemod
│   └── fonts/                 the plates' outlined lettering (SIL OFL 1.1)
├── tests/unit/                the kit's behavioural tests
├── .github/badges.yml         this repository's own badges
├── assets/badges/
│   ├── static/                fixed-value badges (black label), a plate's two files
│   └── dynamic/               health badges and live plates (gold label)
└── docs/
    ├── Badge-Kit.md           the full specification
    ├── Gallery.md             every icon, color, style and print, generated
    └── badges.example.yml     a starter data file to copy
```

</details>

---

## 🛠️ Working On It

For developing the kit itself, in a clone of this repository. Consuming it in
your own repository needs none of this, only the pinned stub above.

```bash
make help        # list every target
make badges      # localize any hotlinks, render every badge, refresh the gallery
make check       # CI gate: self-test, drift check, no hotlink remains
make self-test   # renderer and parser invariants, no repository needed
```

### Releasing

Every stub pins `@v1`, a moving major tag. A version is cut by dispatching
**🏷️ Cut Release** with `vX.Y.Z`: the stub calls the standards' release
workflow, which refuses a commit that is not on the default branch or a
version that does not move forward, proves the action and the kit exist at
the commit and that the self-test passes, then tags the immutable version,
force-moves `v1`, publishes the release with generated notes and prunes the
pages it superseded. Version tags are never deleted, so a full-version pin
keeps resolving. A release that changes what a badge looks like for the same
data bumps the kit version, and every consumer redraws on its next run.

Full specification: [`docs/Badge-Kit.md`](docs/Badge-Kit.md).

---

## 📄 License

MIT. See [`LICENSE`](LICENSE).

The Verdana advance-width tables in `src/badge-kit.py` are derived from the
[`anafanafo`](https://github.com/metabolize/anafanafo) dataset, Copyright (c)
2018 Metabolize LLC, also MIT. [`NOTICE`](NOTICE) records that attribution,
and it travels in the file's own SPDX headers.

The blueprint plates are lettered with outlines of
[Barlow Condensed](https://github.com/jpt/barlow), Copyright 2017 The Barlow
Project Authors, under the SIL Open Font License 1.1, whose text is
[`src/fonts/OFL-Barlow-Condensed.txt`](src/fonts/OFL-Barlow-Condensed.txt).
`NOTICE` records it too.

---

## 🔗 See also

> [!TIP]
> The full specification is [`docs/Badge-Kit.md`](docs/Badge-Kit.md).
> [`tannergolden/banners`](https://github.com/tannergolden/banners) draws the
> header, the footer and the body of a README, and
> [`tannergolden/trophies`](https://github.com/tannergolden/trophies) its
> case, the way this draws its badges: in the same palette, under the same
> rule. [`tannergolden/markdown`](https://github.com/tannergolden/markdown)
> calls all three from one stub. The engineering standards this repository
> follows are published in
> [`tannergolden/standards`](https://github.com/tannergolden/standards), and
> [`tannergolden/path`](https://github.com/tannergolden/path) is the template
> a new repository starts from. If you rename or move a file, update every
> reference to it across the repository to prevent link drift.

---

<div align="center">

**Self-drawn. Self-hosted. Never rate-limited.**

[↑ Back to Top](#top)

<br />

Built with ❤️ by [@tannergolden](https://github.com/tannergolden). Distributed under the MIT License.

</div>
