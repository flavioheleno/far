# freecad-weekly-appimage

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/freecad-weekly-appimage), initially at revision [`91280f750e62665c36e67d1c2a08c2a933a2352c`](https://aur.archlinux.org/cgit/aur.git/commit/?h=freecad-weekly-appimage&id=91280f750e62665c36e67d1c2a08c2a933a2352c). Original maintainer and contributor headers are preserved.

## Package policy

Tracks the upstream FreeCAD weekly AppImage, including the complete dated version, FUSE 2 dependency, launcher, and desktop patch. FAR adds explicit failure handling for the prepare-directory change.

The directory and package base retain AUR's naming. The full declared architecture list is retained, including x86_64. Read `PKGBUILD` and `.SRCINFO` for current runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/freecad-weekly-appimage
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman installs the result. For separate steps, use `makepkg --syncdeps`, inspect `makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe and update diff, and keep Arch updated first.

## Maintenance

FAR tracks upstream GitHub releases directly; AUR is credited only for the initial recipe. `.nvchecker.toml` declares the release source, exact assets, HTTPS hosts, and checksum mappings. Scheduled jobs propose version, source URL, checksum, and generated `.SRCINFO` changes. Recipe customizations and supporting files stay under FAR ownership.

Weekly tags are ordered by their complete date. New builds read the base version from `version.json` at that tag and retain the date in `pkgver`. Missing or ambiguous Linux x86_64 assets stop the update.

Downloads are temporary and discarded; no packages are built or uploaded. Review upstream packaging compatibility and test locally.
