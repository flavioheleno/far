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

Validation scripts and scheduled update automation are added in subsequent
implementation commits, with their documentation in the same commits.
