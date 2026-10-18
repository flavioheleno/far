# tableplus

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/tableplus), initially at revision [`426c310a583a869b3de623d8b854865ac1d27830`](https://aur.archlinux.org/cgit/aur.git/commit/?h=tableplus&id=426c310a583a869b3de623d8b854865ac1d27830). Original maintainer and contributor headers are preserved.

## Package policy

The vendor’s Linux Alpha Debian package is repackaged locally. FAR quotes build paths, removes the duplicate binary installation, and installs the launcher in `/usr/bin/tableplus` as a symlink to `/opt/tableplus/tableplus`, rather than placing package-managed files under `/usr/local`. The local packaging revision is `1.1`; the reviewed overlay must be revisited if AUR changes that packaging revision.

The directory and package base retain AUR's naming. The full declared architecture list is retained, including x86_64. Read `PKGBUILD` and `.SRCINFO` for current runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/tableplus
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman installs the result. For separate steps, use `makepkg --syncdeps`, inspect `makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe and update diff, and keep Arch updated first.

## Maintenance

`.aur.json` records the current AUR revision and the SHA-256 hashes of the maintained recipe/support files. `.SRCINFO` is regenerated locally. Scheduled updates propose AUR changes, including packaging changes at the same version, as a PR. Upstream source checksums and signature verification are retained and checked by makepkg on your machine. GitHub does not download all vendor payloads or build this package.

`far.patch` records FAR's local changes and is reapplied to every new snapshot. A conflict stops the update for manual review.

AUR updates depend on the AUR maintainer publishing a new recipe. Manual/runtime verification belongs on the local machine; a passing metadata check does not establish a successful build or launch.
