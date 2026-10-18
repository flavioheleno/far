# Repository instructions

## Purpose and boundaries

FAR is an AUR-style collection of Arch Linux recipes for local x86_64 builds.
Every package has a directory at `packages/<pkgbase>/`. Keep package-specific
files together; keep shared orchestration in `scripts/`.

- Never add package builds, installation, AppImage execution, binary artifact
  uploads, binary caches, or a pacman binary repository to GitHub Actions.
- Temporary upstream downloads for checksum verification are allowed. Do not
  commit or upload those downloads, build outputs, or extracted sources.
- Keep `PKGBUILD` as the package definition and regenerate `.SRCINFO` with
  `makepkg --printsrcinfo` whenever package metadata changes. Never hand-edit it.
- Preserve imported recipe attribution and record the exact upstream revision in
  the package README. Review imported changes rather than blindly mirroring AUR.
- Use version-specific source URLs, full upstream build identifiers, and SHA-256
  or stronger checksums. Never refresh an unchanged version's checksum silently.
- Each package documents its release channel, asset selection, dependencies,
  local build instructions, and known limitations.
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
- Make atomic Conventional Commits (`docs:`, `feat:`, `fix:`, `ci:`, `test:`).
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
each package's `update.py` implements `select_candidate` and `render_recipe`.

The root README is the entry point for commands and GitHub setup. Follow any
additional package instructions, keeping the recipe-only boundary above intact.
