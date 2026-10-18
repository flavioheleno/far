# FAR — Flavio's Arch Repository

Personal Arch Linux package recipes for an x86_64 machine. GitHub Actions keeps
the recipes current through pull requests. Build and install packages locally
with [rua](https://github.com/vn971/rua) or `makepkg` and `pacman`.

## Repository contract

- Each package lives in `packages/<pkgbase>/` with its `PKGBUILD`, generated
  `.SRCINFO`, update configuration, and packaging notes.
- Git tracks recipes, metadata, patches, documentation, and automation.
- GitHub Actions performs recipe checks and upstream update discovery. It never
  builds or installs packages, executes upstream AppImages, uploads package
  artifacts, or caches downloaded binaries.
- An updater may download upstream files into temporary storage to verify their
  checksums. Those files are discarded when the job ends.
- Updates arrive as one reviewable pull request per package. Merge decisions and
  local installation remain manual.

## Layout

```text
packages/              One directory per package base
scripts/               Recipe validation and update orchestration
tests/                 Tests for update selection and failure handling
.github/workflows/     Validation and scheduled recipe updates
AGENTS.md              Instructions for future repository work
```

## Packages

| Package | Architecture | Release channel |
| --- | --- | --- |
| [bambustudio-appimage](packages/bambustudio-appimage/) | x86_64 | Stable and beta |

## Local build and installation

Clone the repository and review the package recipe and its history. After pulling
updates with `git pull --ff-only`, use rua's local-directory command:

```sh
rua builddir ./packages/bambustudio-appimage
```

Or enter the package directory and use `makepkg --syncdeps`, then install the
resulting local archive with `sudo pacman -U <package-file>`. `makepkg -si`
combines those steps. See the package README for dependencies, installation
details, and manual runtime checks.

`rua install` and `rua upgrade` normally fetch AUR recipes. They do not discover
FAR's GitHub updates. Use the local checkout when consuming FAR recipes, and keep
your AUR helper from independently replacing FAR-managed packages.

## Metadata maintenance

On Arch Linux with `base-devel` installed, regenerate package metadata without
downloading sources or building a package:

```sh
cd packages/bambustudio-appimage
makepkg --printsrcinfo > .SRCINFO
```

## Recipe checks and updates

Requirements: Arch Linux, Python 3.11+, `base-devel`, `shellcheck`, and `git`.
The Python tooling uses only the standard library. Commands work from any
working directory; the paths below assume the repository root.

```sh
./scripts/check-packages
python3 -m unittest discover -s tests -v
./scripts/update-packages --list
./scripts/update-packages bambustudio-appimage
./scripts/update-packages --apply bambustudio-appimage
```

The checker runs Bash syntax checks, ShellCheck (excluding package metadata and
makepkg-provided variable false positives), and compares regenerated `.SRCINFO`
with the committed file. These checks never call `build()`, `prepare()`, or
`package()` and do not download package sources. Metadata generation does source
the recipe as shell code: only evaluate recipes you trust.

The updater defaults to a read-only preview. It reads the GitHub repository,
release channel, and normalization rules from `.nvchecker.toml`, then invokes the
package's `update.py` adapter. It downloads and hashes new assets before proposing
changes. `--apply` updates `PKGBUILD` and regenerates `.SRCINFO`, rolling back those
files if validation fails. Both commands accept one or more package bases;
omitting them selects all packages. Failures are reported independently and
produce a nonzero exit code.

Already-current recipes use GitHub's asset digest to detect upstream changes
without downloading the asset again. Use `--verify-current` to force a fresh
download and hash; assets without a published digest are always downloaded.
Changed content at the same version, ambiguous assets, and downgrades require
manual review. Temporary downloads are hashed as a stream and never saved.
An optional `GH_TOKEN` raises the GitHub API rate limit; it is not passed to
`makepkg`. Release discovery follows up to 1,000 release entries, failing visibly
instead of silently truncating a larger history.

For reproducible diagnosis, `--releases-json <file>` accepts a saved GitHub REST
release-list response for one package. `--report <file>` writes a JSON summary,
including failures. These options do not bypass asset integrity checks.

The offline unit tests exercise beta selection, full build versions, historical
asset names, ambiguous/missing assets, source integrity, downgrade protection,
rollback, credential stripping, and repeat-run behavior. They build no packages
and contact no external services.

Scheduled GitHub automation is added in the next implementation commit.
