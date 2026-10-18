# fritzing

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/fritzing), initially at revision [`045535f8160b983a754e0d5d82b345a7fd2093ae`](https://aur.archlinux.org/cgit/aur.git/commit/?h=fritzing&id=045535f8160b983a754e0d5d82b345a7fd2093ae). Original maintainer and contributor headers are preserved.

## Package policy

Builds Fritzing **from source on your machine**. The application and parts repositories are pinned to separate commits, with the AUR patches, ngspice/Qt dependencies, and install hook retained. FAR adds explicit failure handling for directory changes. VCS checksum exceptions correspond to those pinned Git revisions; the other sources retain their checksums.

The directory and package base retain AUR's naming. The full declared architecture list is retained, including x86_64. Read `PKGBUILD` and `.SRCINFO` for current runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/fritzing
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman installs the result. For separate steps, use `makepkg --syncdeps`, inspect `makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe and update diff, and keep Arch updated first.

## Maintenance

`.aur.json` records the current AUR revision and the SHA-256 hashes of the maintained recipe/support files. `.SRCINFO` is regenerated locally. Scheduled updates propose AUR changes, including packaging changes at the same version, as a PR. Upstream source checksums and signature verification are retained and checked by makepkg on your machine. GitHub does not download all vendor payloads or build this package.

`far.patch` records FAR's local changes and is reapplied to every new snapshot. A conflict stops the update for manual review.

AUR updates depend on the AUR maintainer publishing a new recipe. Manual/runtime verification belongs on the local machine; a passing metadata check does not establish a successful build or launch.
