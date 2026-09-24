# 🧪 Tests - the kit's suites

The kit's behavioural tests live in `unit/`: `test_badge_kit.py` for the renderer and `test_localize_badges.py` for the codemod, each loading its program straight from `../../src/`. `make test` is what CI runs as the `test-command` in `.github/workflows/checks.yml`: the renderer's self-test, the committed-SVG drift check, the hotlink gate, these suites, and then the repository script tests under `.github/scripts/`. Everything is stdlib `unittest`, discovered by filename, so a new `test_*.py` beside the existing ones runs without being named anywhere.

| Folder         | Put (and look for)                                                           |
| :------------- | :--------------------------------------------------------------------------- |
| `unit/`        | Fast, isolated tests of pure logic (co-locating next to source is fine too). |
| `integration/` | Tests that cross a real boundary: database, filesystem, HTTP.                |
| `e2e/`         | Full user-journey tests against a running system.                            |

The binding standard is the canonical [Testing Strategy](https://github.com/tannergolden/standards/blob/Development/docs/distribution/Testing-Strategy.md); the fill-in guidelines under `docs/templates/technical/testing/` are seeded for your own conventions.

This directory is **yours from the first commit**. Nothing here syncs, and nothing upstream will ever write to it or delete from it - there is no sync engine to protect it from.
