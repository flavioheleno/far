# freecad-weekly-appimage

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/freecad-weekly-appimage), initially at revision [`91280f750e62665c36e67d1c2a08c2a933a2352c`](https://aur.archlinux.org/cgit/aur.git/commit/?h=freecad-weekly-appimage&id=91280f750e62665c36e67d1c2a08c2a933a2352c). Original maintainer and contributor headers are preserved.

## Package policy

Tracks the AUR-maintained FreeCAD weekly AppImage, including the complete dated version, FUSE 2 dependency, launcher, and desktop patch. FAR adds explicit failure handling for the prepare-directory change.

The directory and package base retain AUR's naming. The full declared architecture list is retained, including x86_64. Read `PKGBUILD` and `.SRCINFO` for current runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/freecad-weekly-appimage
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman installs the result. For separate steps, use `makepkg --syncdeps`, inspect `makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe and update diff, and keep Arch updated first.

## Maintenance

`.aur.json` records the current AUR revision and the SHA-256 hashes of the maintained recipe/support files. `.SRCINFO` is regenerated locally. Scheduled updates propose AUR changes, including packaging changes at the same version, as a PR. Upstream source checksums and signature verification are retained and checked by makepkg on your machine. GitHub does not download all vendor payloads or build this package.

`far.patch` records FAR's local changes and is reapplied to every new snapshot. A conflict stops the update for manual review.

AUR updates depend on the AUR maintainer publishing a new recipe. Manual/runtime verification belongs on the local machine; a passing metadata check does not establish a successful build or launch.
