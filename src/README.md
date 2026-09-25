# 💻 Source - the kit's two programs

The badge kit is two stdlib-only Python programs at the top of this folder, sharing one output tree:

| File                 | Job                                                                                  |
| :------------------- | :----------------------------------------------------------------------------------- |
| `badge-kit.py`       | The renderer. Turns `.github/badges.yml` into committed SVGs, and draws the gallery. |
| `localize-badges.py` | The codemod. Rewrites `img.shields.io` hotlinks in Markdown into committed SVGs.     |

`fonts/` holds the outlines the blueprint plates are lettered with: Barlow Condensed SemiBold and Bold as SVG paths, one JSON file read on the first plate a run draws, with the SIL Open Font License it ships under beside it.

Both resolve the repository they render **for** from `GITHUB_WORKSPACE`, else the working directory, never from their own location: as a composite action the kit sits in its own checkout while the consumer's repository is the workspace. `action.yml` at the repository root is how a consumer calls them (`uses: tannergolden/emblems@v1`), and the [Badge Kit specification](../docs/Badge-Kit.md) is the contract they implement. Every SVG is stamped with `KIT_VERSION`, and the self-test pins one canonical render to `GOLDEN_SHA`, so rendered output cannot change without someone bumping the version knowingly.

The scaffold's layers are still here for whatever grows next - the template imposes a layout, not a stack:

| Folder    | Put (and look for)                                                         |
| :-------- | :------------------------------------------------------------------------- |
| `app/`    | The application layer: entry points, use-cases, orchestration.             |
| `domain/` | The domain layer: entities, business rules, pure logic (no I/O).           |
| `infra/`  | The infrastructure layer: persistence, transport, adapters to the outside. |

Standards to follow while filling it in: the fill-in [Source Code](../docs/templates/technical/Source-Code.md) and [Technology Stack & Tooling](../docs/templates/technical/Technology-Stack-&-Tooling.md) documents seeded under `docs/templates/technical/` - instantiate them with your decisions.

This directory is **yours from the first commit**. Nothing here syncs, and nothing upstream will ever write to it or delete from it - there is no sync engine to protect it from.
