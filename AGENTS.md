# Repository instructions

## Purpose and boundaries

FAR is an AUR-style collection of Arch Linux recipes for local x86_64 builds.
Every package has a directory at `packages/<pkgbase>/`. Keep package-specific
files together; keep shared orchestration in `scripts/`.

- Never build or install managed packages, execute their AppImages, upload
  binary artifacts, cache binaries, or publish a pacman binary repository from
  GitHub Actions. Installing lint/metadata tools from official Arch repositories
  in a disposable CI container is allowed.
- Temporary upstream downloads for checksum verification are allowed. Do not
  commit or upload those downloads, build outputs, or extracted sources.
- Keep `PKGBUILD` as the package definition and regenerate `.SRCINFO` with
  `makepkg --printsrcinfo` whenever package metadata changes. Never hand-edit it.
- Preserve imported recipe attribution and record the exact initial revision in
  the package README for provenance only. Track upstream projects directly;
  never poll or synchronize AUR recipes. Use AUR's established pkgbase names.
- Use version-specific source URLs, full upstream build identifiers, and SHA-256
  or stronger checksums. Never refresh an unchanged version's checksum silently.
  Preserve documented signed-metadata and pinned-VCS checksum exceptions from
  reviewed initial recipes; do not add SKIP for ordinary binary payloads.
- Each package documents its release channel, asset selection, dependencies,
  local build instructions, and known limitations.
- Sublime Text is intentionally excluded; use its official pacman repository.
  Do not recreate a local Sublime Text recipe as part of routine maintenance.
- Never build or install packages on the user's machine unless specifically
  requested. Metadata checks and updater tests are the normal verification.

## Automation

Prefer standard Arch tools and Python's standard library. Introduce dependencies
only when they solve a concrete problem. New update adapters must reject missing
or ambiguous assets, downgrades, unexpected source URLs, and checksum mismatches.
Keep update runs idempotent. Failure in one package must not hide other results.

Treat PKGBUILDs and update adapters as executable code. Run metadata evaluation
without write credentials or secrets. Keep pull-request writing separate from
recipe evaluation. Pin external Actions to full commit SHAs, use least-privilege
permissions, and maintain their pins through Dependabot. Do not execute PR code
with `pull_request_target` or another privileged event.

## Working conventions

- Read the root README and relevant package README before editing.
- Update documentation in the same commit as the behavior it describes. Describe
  current functionality rather than future promises.
- Update both root package tables when adding or removing packages. Keep declared
  architectures consistent with `.SRCINFO`, and distinguish retained architecture
  support from runtime validation on the local x86_64 machine. Keep changing
  versions, source pins, and checksums authoritative in `PKGBUILD`/`.SRCINFO`;
  label historical verification notes with the initial version.
- Make atomic Conventional Commits (`docs:`, `feat:`, `fix:`, `ci:`, `test:`,
  `chore:` for routine version bumps and removals).
  Stage named files and inspect the staged diff. Do not include unrelated work.
- Use `rg` for searches. When RTK is installed, prefix shell tool calls with
  `rtk` (use `rtk proxy` for commands without a dedicated wrapper).
- Keep scripts usable from any working directory. Fail with useful messages and
  nonzero exit codes. Keep generated files deterministic.
- Add focused tests for nontrivial selection, integrity, and update logic. Do not
  add package compilation to tests. Run the documented checks before committing.
- Keep secrets, tokens, personal configuration, downloads, and build products out
  of Git. Do not modify system configuration as part of repository maintenance.

Before committing recipe or updater changes, run `./scripts/check-packages` and
`python3 -m unittest discover -s tests -v`. Both are recipe-only checks. Run a
preview of affected packages against saved metadata when available; do not use
live upstream data in unit tests. `scripts/far.py` contains shared maintenance;
the Bambu Studio/Extrudo `source = "github"` packages' `update.py` implements
`select_candidate` and `render_recipe`. Other packages use `scripts/upstreams.py` discovery and
`scripts/far_upstream.py` for source mapping, bounded downloads, rollback, and
literal publication checks. Configuration declares first-party hosts, version/URL
assignments, and exact checksum slots. Preserve every declared architecture and
full vendor build identifier. Maintain packaging customizations directly; there
are no AUR overlays or snapshot manifests. Supporting files, dependency changes,
and signing keys require explicit review outside automated update PRs. Spotify
must retain wget DLAGENTS, its epoch, and its signed metadata verification chain.
Fritzing watches upstream source-version bump commits, not GitHub Releases:
verify versions from immutable source metadata, pin the exact bump commit, and
retain the parts pin for explicit compatibility review. Never follow arbitrary
development commits within the same version or claim a bump proves a public
release.

`.nvchecker.toml` is FAR's own configuration, read with Python's `tomllib`; the
workflow does not invoke nvchecker. Available shared modes are `github-assets`,
`freecad-weekly`, `debian`, `saleae`, and `fritzing`. Keep new adapters compatible
with the publication version format (numeric dotted components, optionally an
underscore and numeric dotted date), or extend that format with focused tests.
Reset `pkgrel` on new upstream versions; bump it manually for packaging-only
changes and preserve epochs. Automated PRs may modify only `PKGBUILD` and
`.SRCINFO`. Changes to updater configuration, documentation, or supporting files
belong in a separate reviewed maintenance commit.

Run `actionlint` after workflow changes. `scripts/workflow.py` is the boundary
between unprivileged update preparation and PR publication: keep its patch path
allowlist, payload bounds, and no-recipe-execution publication behavior intact.

The root README is the entry point for commands and GitHub setup. Follow any
additional package instructions, keeping the recipe-only boundary above intact.
