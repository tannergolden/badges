#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Tanner Golden
# SPDX-License-Identifier: MIT
"""
Localize shields.io badges into committed Badge-Kit SVGs.

The repository's philosophy is zero live-service hotlinks: every render-time
asset is a committed SVG drawn by our own generator. Document headers were
the last holdout, still fetching their four classification badges (Status,
Role, Context, License) from img.shields.io on every view. This codemod
finishes the migration for the whole tree:

  1. Find every img.shields.io badge referenced from a Markdown file.
  2. Parse its label / message / color / style, and render it once with the
     Badge Kit into assets/badges/static/<slug>.svg - using the house icon
     convention (Status->pulse, Role->book, Context->layers, License->scale)
     so the localized headers match the README masthead.
  3. Rewrite the reference to an ABSOLUTE raw.githubusercontent.com URL for
     the committed SVG, pinned to the default branch.

Why absolute, not relative: GitHub only rewrites RELATIVE markdown image
paths in its main blob/README views. Its other rendering surfaces - the
pull-request rich diff, the security-policy tab and the community-health
special views, and client-side soft navigation - leave them unresolved, so
a relative badge renders as a broken image exactly where these files are
most often read. An absolute raw URL renders in every view (GitHub proxies
it through camo like any absolute image), which is how this repository's
profile README already embeds its metric SVGs. The identity in the URL is
resolved dynamically (GITHUB_REPOSITORY, then the git remote, then the
template's own name), so a derived repository regenerates the references
for itself with `make badges`; the Day-0 rebrand rewrites the committed
form too. Trade-off, documented in Badge-Kit.md: on a private repository
camo cannot fetch raw content, but relative paths break in half the views
regardless, so absolute is strictly more robust.

The rendered SVGs are committed. "Use this template" copies assets/ at
generation, so a derived repository receives them; the doc badges are static
classification text (Role-Guide is identical in every repository), so they
never need per-repo regeneration. check-docs-style.py already treats a
committed Badge-Kit SVG referenced by a self raw URL as a first-class
header badge (the same resolution the profile README relies on).

Usage:
  python3 scripts/localize-badges.py            # localize + render (idempotent)
  python3 scripts/localize-badges.py --check     # CI gate: no shields.io URL
                                                 # or relative doc-badge ref
                                                 # remains, and every referenced
                                                 # doc badge exists and is current
Run via `make badges` (which also renders .github/badges.yml).
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import urllib.parse
from pathlib import Path

def workspace() -> Path:
    """The repository this run localizes badges IN (see badge-kit.workspace)."""
    ws = os.environ.get("GITHUB_WORKSPACE", "")
    if ws and Path(ws).is_dir():
        return Path(ws)
    return Path.cwd()


KIT_DIR = Path(__file__).resolve().parent

# Where this run points. Set by configure(): from the CLI flags in main(), and
# by badge-kit.py before it asks which files this codemod owns, so the two
# programs always agree on one tree. Module import configures the defaults.
REPO_ROOT: Path
DATA_FILE: Path        # the badge data file (default .github/badges.yml)
OUT_DIR: Path          # the badge tree (default assets/badges)
OUT_REL: str           # OUT_DIR relative to REPO_ROOT, posix, for URLs/regex
DOC_BADGE_DIR: Path    # OUT_DIR/static - classification badges are fixed-value
ROOT_README: Path      # the one file allowed to keep relative badge refs
_DOC_REF_RE: "re.Pattern[str]"


def configure(root=None, data=None, out=None) -> None:
    """Point the codemod at a repository and its badge tree.

    Classification badges live in OUT_DIR/static (the type split: static/ vs
    dynamic/). This codemod owns them; badge-kit.py reserves them through
    managed_doc_filenames() so its own pruning never touches them.

    The front-page README renders in GitHub's blob/index view, where RELATIVE
    image paths resolve, so its masthead may embed a committed badge by
    relative path. Every other Markdown file may be read where relative paths
    break (rich diff, security tab, the off-repository profile), so those must
    use the absolute raw URL.
    """
    global REPO_ROOT, DATA_FILE, OUT_DIR, OUT_REL, DOC_BADGE_DIR, ROOT_README, _DOC_REF_RE
    REPO_ROOT = Path(root).resolve() if root else workspace().resolve()
    DATA_FILE = Path(data) if data else REPO_ROOT / ".github" / "badges.yml"
    if not DATA_FILE.is_absolute():
        DATA_FILE = REPO_ROOT / DATA_FILE
    OUT_DIR = Path(out) if out else REPO_ROOT / "assets" / "badges"
    if not OUT_DIR.is_absolute():
        OUT_DIR = REPO_ROOT / OUT_DIR
    try:
        OUT_REL = OUT_DIR.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        # An output tree outside the repository has no in-repo path to write
        # into a reference; keep the conventional one so the URLs stay sane.
        OUT_REL = "assets/badges"
    DOC_BADGE_DIR = OUT_DIR / "static"
    ROOT_README = REPO_ROOT / "README.md"
    # Any existing reference to a committed doc badge, in every form this
    # codemod (or a hand edit) may have produced: relative with any number of
    # ../ hops, repo-absolute, or an absolute raw URL for any owner/repo/branch.
    # Group 1 is the badge filename. Used to NORMALIZE references.
    _DOC_REF_RE = re.compile(
        r"(?:https?://raw\.githubusercontent\.com/[^/\s)]+/[^/\s)]+/[^\s)]+?/)?"
        r"(?:(?:\.\./)+|/)?" + re.escape(OUT_REL)
        + r"/(?:doc|static)/([a-z0-9][a-z0-9.-]*\.svg)")


configure()

# Load the Badge Kit (its filename has a hyphen, so import by path).
_spec = importlib.util.spec_from_file_location(
    "badge_kit", KIT_DIR / "badge-kit.py")
badge_kit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(badge_kit)

# The house icon convention for the four classification badges, matching the
# README masthead (see .github/badges.yml). A label not listed here renders
# with no icon.
LABEL_ICON = {
    "status": "pulse",
    "role": "book",
    "context": "layers",
    "license": "scale",
    # Common non-header example badges that appear in the fill-in scaffolds.
    "package": "package",
    "code style": "code",
    "code_style": "code",
    "conventional commits": "commit",
    "speed": "flame",
    "chat": "chat",
}

# shields color names -> Badge-Kit palette tokens (exact brand hexes map
# straight through; anything unrecognized is passed as a raw #hex, which the
# kit also accepts).
HEX_TO_TOKEN = {
    "2EA043": "green", "F1E05A": "yellow", "FE5196": "pink",
    "9C27B0": "purple", "D73A49": "red", "3366FF": "blue",
    "C0A062": "gold", "8A8B2C": "olive", "1F9E8F": "teal",
    "E36209": "orange", "57606A": "slate", "8B6CFF": "violet",
}
NAME_TO_TOKEN = {
    "green": "green", "brightgreen": "green", "success": "green",
    "yellow": "yellow", "yellowgreen": "olive", "important": "orange",
    "orange": "orange", "red": "red", "critical": "red", "blue": "blue",
    "informational": "blue", "lightgrey": "slate", "gray": "slate",
    "grey": "slate", "blueviolet": "violet", "purple": "purple",
    "ff69b4": "pink", "pink": "pink",
}


def _unescape_field(field: str) -> str:
    """Undo shields' path escaping for one label/message/color field."""
    # Order matters: protect doubled escapes, then single-char meanings.
    field = field.replace("__", "\x01").replace("_", " ").replace("\x01", "_")
    return urllib.parse.unquote(field)


def parse_shields(url: str) -> dict | None:
    """Parse a shields.io badge URL into label/message/colors/style/icon.

    Returns None for shields endpoints that are not static /badge/ badges
    (e.g. dynamic /github/... endpoints), which this codemod does not localize.
    """
    m = re.match(r"https?://img\.shields\.io/badge/(.+)$", url)
    if not m:
        return None
    rest = m.group(1)
    path, _, query = rest.partition("?")
    if path.endswith(".svg"):
        path = path[:-4]
    # Split the three dash-separated fields, treating `--` as an escaped dash.
    protected = path.replace("--", "\x00")
    parts = [p.replace("\x00", "-") for p in protected.split("-")]
    if len(parts) < 2:
        return None
    color_raw, message_raw = parts[-1], parts[-2]
    label_raw = "-".join(parts[:-2]) if len(parts) >= 3 else ""
    label = _unescape_field(label_raw)
    message = _unescape_field(message_raw)

    params = urllib.parse.parse_qs(query)
    # The kit now draws plastic itself, so a plastic hotlink keeps its shape
    # through a migration instead of being flattened. `social` has no
    # equivalent here (it is a different object, not a different chip), so it
    # still lands on flat.
    style_map = {"for-the-badge": "for-the-badge", "flat": "flat",
                 "flat-square": "flat-square", "plastic": "plastic",
                 "social": "flat"}
    style = style_map.get((params.get("style") or ["flat"])[0], "flat")

    def to_color(raw: str, default: str) -> str:
        raw = raw.strip()
        if not raw:
            return default
        up = raw.upper()
        if re.fullmatch(r"[0-9A-F]{6}", up):
            return HEX_TO_TOKEN.get(up, f"#{up}")
        if re.fullmatch(r"[0-9A-F]{3}", up):
            # Expand shorthand (#abc -> #aabbcc) and consult the HEX map, the
            # same as the 6-hex branch; the name map has no hex keys.
            full = "".join(ch * 2 for ch in up)
            return HEX_TO_TOKEN.get(full, f"#{up}")
        return NAME_TO_TOKEN.get(raw.lower(), "slate")

    message_color = to_color(color_raw, "slate")
    label_hex = (params.get("labelColor") or params.get("labelcolor") or [""])[0]
    if label_hex:
        label_color = to_color(label_hex, "black")
    else:
        # The house style for classification headers is a black label; a
        # bare shields badge (grey label) becomes black to match.
        label_color = "black"
    icon = LABEL_ICON.get(label.lower(), None)
    return {"label": label, "message": message, "label_color": label_color,
            "message_color": message_color, "icon": icon, "style": style}


def _signature(spec: dict) -> tuple:
    return (spec["label"], spec["message"], spec["label_color"],
            spec["message_color"], spec["icon"], spec["style"])


def _base_slug(spec: dict) -> str:
    def kebab(s: str) -> str:
        s = re.sub(r"[^0-9a-zA-Z]+", "-", s.strip().lower()).strip("-")
        return s or "x"
    base = f"{kebab(spec['label'])}-{kebab(spec['message'])}".strip("-")
    return base or "badge"


def _sig_hash(sig: tuple) -> str:
    import hashlib
    return hashlib.md5("|".join(str(x) for x in sig).encode()).hexdigest()[:6]


# Shields URLs embedded in Markdown image or <img> syntax.
_SHIELDS_RE = re.compile(r"https?://img\.shields\.io/badge/[^\s)\"'>]+")



def tracked_markdown() -> list[Path]:
    import subprocess
    out = subprocess.run(["git", "ls-files", "*.md", "*.markdown"],
                         cwd=REPO_ROOT, capture_output=True, text=True).stdout
    # ls-files reads the INDEX: a tracked file deleted from the worktree
    # but not yet staged (mid-refactor, or right after Day-0 init removes
    # the law docs) would otherwise crash every read below.
    return [
        p for line in out.splitlines() if line.strip()
        if (p := REPO_ROOT / line).is_file()
    ]


def repo_identity() -> str:
    """owner/repo, resolved like badge-sync.py: Actions env first, then the
    git remote, then the template's own name (badge-sync rebrands the
    committed URLs downstream even when this script never re-runs)."""
    env = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in env:
        return env
    import subprocess
    url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=REPO_ROOT,
                         capture_output=True, text=True).stdout.strip().rstrip("/")
    m = re.search(r"github\.com[:/]([^/]+)/(.+?)(?:\.git)?$", url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # Neither Actions nor a GitHub remote could name the repository. Emit a
    # VISIBLY wrong placeholder rather than guessing: a silent wrong owner
    # would commit badge URLs pointing at somebody else's repository.
    print("::warning::could not resolve owner/repo from GITHUB_REPOSITORY or "
          "the git remote; badge URLs will contain OWNER/REPO placeholders",
          file=sys.stderr)
    return "OWNER/REPO"


def default_branch() -> str:
    """The default branch the raw URLs pin to. origin/HEAD when the clone
    knows it (a full clone of any repository does), then the ref Actions is
    running, then `main` - the ecosystem default, so a consumer whose clone
    is too shallow to carry origin/HEAD still gets a working URL."""
    import subprocess
    ref = subprocess.run(["git", "symbolic-ref", "-q", "refs/remotes/origin/HEAD"],
                         cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    if ref.startswith("refs/remotes/origin/"):
        return ref[len("refs/remotes/origin/"):]
    return os.environ.get("GITHUB_REF_NAME") or "main"


def canonical_base() -> str:
    return (f"https://raw.githubusercontent.com/{repo_identity()}/"
            f"{default_branch()}/{OUT_REL}/static/")


def own_badge_files() -> set[str]:
    """Basenames of THIS repository's own badges (from .github/badges.yml).
    They share the static/ and dynamic/ folders but belong to the Badge Kit,
    not the doc-header library - so localize must never treat a reference to
    one as a doc badge: the README embeds them by relative path (correct for
    the main blob view), and rewriting those to absolute would be wrong."""
    try:
        own = {f"{b['name']}.svg" for b in badge_kit.load_badges(DATA_FILE)}
    except Exception:
        own = set()
    # The gallery is generated rather than listed, but it is no less this
    # repository's own: its page references the badges beside it relatively,
    # which is correct, so they must never be rewritten or flagged.
    try:
        own |= badge_kit.gallery_filenames()
    except Exception:
        pass
    return own


def managed_doc_filenames(root=None, data=None, out=None) -> set[str]:
    """Committed doc-badge basenames this codemod owns - every badge referenced
    by a shields.io URL (to be localized) or by an existing doc-badge reference
    anywhere in the tracked Markdown. badge-kit.py calls this to RESERVE these
    files in the shared static/ folder, so its own pruning never deletes or
    flags a classification/posture badge it does not manage. It passes the
    tree it is rendering into, so both programs look at the same files."""
    from collections import defaultdict
    if root is not None or data is not None or out is not None:
        configure(root, data, out)
    files = tracked_markdown()
    sig_spec: dict[tuple, dict] = {}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for url in _SHIELDS_RE.findall(text):
            spec = parse_shields(url)
            if spec is not None:
                sig_spec[_signature(spec)] = spec
    names: set[str] = set()
    base_sigs: dict[str, list[tuple]] = defaultdict(list)
    for sig, spec in sig_spec.items():
        base_sigs[_base_slug(spec)].append(sig)
    for base, sigs in base_sigs.items():
        if len(sigs) == 1:
            names.add(f"{base}.svg")
        else:
            for sig in sigs:
                names.add(f"{base}-{_sig_hash(sig)}.svg")
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in _DOC_REF_RE.finditer(text):
            names.add(m.group(1))
    return names - own_badge_files()


def localize(check: bool) -> int:
    files = tracked_markdown()
    # This repository's own badges (badges.yml) share static//dynamic/ but are
    # the Badge Kit's, not doc-library badges: never rewrite or flag them.
    own = own_badge_files()
    # Pass 1: collect every distinct badge SIGNATURE (identical badges dedupe
    # onto one committed file) and remember which URL maps to which signature.
    sig_spec: dict[tuple, dict] = {}
    url_sig: dict[str, tuple] = {}
    unparsed: list[tuple[Path, str]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for url in _SHIELDS_RE.findall(text):
            if url in url_sig:
                continue
            spec = parse_shields(url)
            if spec is None:
                unparsed.append((path, url))
                continue
            sig = _signature(spec)
            sig_spec[sig] = spec
            url_sig[url] = sig

    # Assign a filename per signature: clean base slug when unique, base +
    # short hash only when two distinct badges would share a base slug.
    from collections import defaultdict
    base_sigs: dict[str, list[tuple]] = defaultdict(list)
    for sig, spec in sig_spec.items():
        base_sigs[_base_slug(spec)].append(sig)
    sig_filename: dict[tuple, str] = {}
    for base, sigs in base_sigs.items():
        if len(sigs) == 1:
            sig_filename[sigs[0]] = f"{base}.svg"
        else:
            for sig in sigs:
                sig_filename[sig] = f"{base}-{_sig_hash(sig)}.svg"

    # Render every needed badge.
    missing_or_stale: list[str] = []
    if not check:
        DOC_BADGE_DIR.mkdir(parents=True, exist_ok=True)
    for sig, spec in sig_spec.items():
        svg = badge_kit.render(spec["label"], spec["message"],
                               spec["label_color"], spec["message_color"],
                               spec["icon"], spec["style"]) + "\n"
        out = DOC_BADGE_DIR / sig_filename[sig]
        if not out.exists() or out.read_text(encoding="utf-8") != svg:
            if check:
                missing_or_stale.append(str(out.relative_to(REPO_ROOT)))
            else:
                out.write_text(svg, encoding="utf-8")

    # Rewrite each file's shields URLs to the canonical ABSOLUTE raw URL of
    # the committed SVG, and NORMALIZE any existing doc-badge reference
    # (relative, repo-absolute, or a stale/foreign raw URL) to the same
    # canonical base - relative paths render broken in GitHub's rich-diff,
    # security-policy, and soft-navigation views (see the module docstring).
    base = canonical_base()
    changed_files = 0
    relative_refs: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        new = text
        # The front-page README may keep committed badges relative (see
        # ROOT_README); everywhere else, only our own badges stay relative.
        is_root_readme = path == ROOT_README
        for url, sig in url_sig.items():
            if url not in new:
                continue
            new = new.replace(url, base + sig_filename[sig])
        new = _DOC_REF_RE.sub(
            lambda m: m.group(0) if (m.group(1) in own or is_root_readme)
            else base + m.group(1), new)
        if new != text and not check:
            path.write_text(new, encoding="utf-8")
            changed_files += 1
        if check:
            # A relative doc-badge reference is a failure in itself: it only
            # renders in the main blob views. (Absolute raw URLs for any
            # identity pass - a freshly generated repo carries the template's
            # until Day-0 init rebrands them.)
            for m in _DOC_REF_RE.finditer(text):
                if (not is_root_readme and m.group(1) not in own
                        and not m.group(0).startswith("http")):
                    relative_refs.append(f"{path.relative_to(REPO_ROOT)}: {m.group(0)}")
            # Every referenced doc badge (not one of our own) must exist.
            for m in _DOC_REF_RE.finditer(text):
                if m.group(1) not in own and not (DOC_BADGE_DIR / m.group(1)).is_file():
                    missing_or_stale.append(f"{OUT_REL}/static/{m.group(1)} "
                                            f"(referenced by {path.relative_to(REPO_ROOT)})")
    # In check mode, any residual shields URL (parsed or not) is a failure.
    still = []
    for path in files:
        if _SHIELDS_RE.search(path.read_text(encoding="utf-8")):
            still.append(str(path.relative_to(REPO_ROOT)))

    if check:
        problems = []
        if missing_or_stale:
            problems.append(f"{len(missing_or_stale)} doc-badge SVG(s) missing or "
                            f"stale (run scripts/localize-badges.py): "
                            f"{', '.join(sorted(set(missing_or_stale))[:8])}")
        if relative_refs:
            problems.append(f"{len(relative_refs)} RELATIVE doc-badge reference(s) "
                            f"(broken in GitHub's rich-diff/security-policy views; "
                            f"run scripts/localize-badges.py to normalize): "
                            f"{', '.join(sorted(set(relative_refs))[:6])}")
        if still:
            problems.append(f"{len(still)} file(s) still reference img.shields.io: "
                            f"{', '.join(sorted(set(still))[:8])}")
        if problems:
            for p in problems:
                print(f"::error::{p}", file=sys.stderr)
            return 1
        print(f"Badge localization check passed - no shields.io hotlink and no "
              f"relative doc-badge reference remains.")
        return 0

    if unparsed:
        for path, url in unparsed:
            print(f"::warning::left a non-static shields endpoint untouched in "
                  f"{path.relative_to(REPO_ROOT)}: {url}")
    print(f"Localized {len(sig_spec)} shields.io badge(s) into "
          f"{OUT_REL}/static across {changed_files} file(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Localize shields.io badges into committed SVGs.")
    ap.add_argument("--check", action="store_true",
                    help="verify no shields hotlink remains and every doc badge is current")
    ap.add_argument("--root", type=Path, default=None,
                    help="repository to localize (default: GITHUB_WORKSPACE, else the "
                         "working directory)")
    ap.add_argument("--data", type=Path, default=None,
                    help="badge data file whose entries are never treated as doc "
                         "badges (default: .github/badges.yml under --root)")
    ap.add_argument("--out", type=Path, default=None,
                    help="badge tree to render into (default: assets/badges under --root)")
    args = ap.parse_args(argv)
    configure(args.root, args.data, args.out)
    return localize(args.check)


if __name__ == "__main__":
    raise SystemExit(main())
