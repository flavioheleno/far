# freecad-weekly-appimage

Arch recipe imported from
[AUR](https://aur.archlinux.org/packages/freecad-weekly-appimage), initially at
revision
[`91280f750e62665c36e67d1c2a08c2a933a2352c`](https://aur.archlinux.org/cgit/aur.git/commit/?h=freecad-weekly-appimage&id=91280f750e62665c36e67d1c2a08c2a933a2352c).
Original maintainer and contributor headers are preserved.

## Package policy

Tracks
[FreeCAD's weekly GitHub releases](https://github.com/FreeCAD/FreeCAD/releases),
retaining the complete dated version, FUSE 2 dependency, launcher, and desktop
patch. Local `prepare()` executes the AppImage's extraction mode to read its
desktop file, icons, and MIME metadata. `/usr/bin/freecad` launches the AppImage
installed under `/opt/appimages/`. FAR's directory-change failure handling is
kept directly in the recipe; CI never executes the AppImage.

The recipe targets Arch Linux `x86_64`. Read [PKGBUILD](PKGBUILD) and [.SRCINFO](.SRCINFO) for current
versions and runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/freecad-weekly-appimage
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman
installs the result. For separate steps, use `makepkg --syncdeps`, inspect
`makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe
and update diff, and keep Arch updated first.

## Maintenance

FAR tracks upstream GitHub releases directly; AUR is credited only for the
initial recipe. `.nvchecker.toml` declares the release source, exact assets,
HTTPS hosts, and checksum mappings. Scheduled jobs propose version, source URL,
checksum, and generated `.SRCINFO` changes. Recipe customizations and supporting
files stay under FAR ownership.

Weekly tags are ordered by their complete date. New builds read the base version
from `version.json` at that tag and retain the date in `pkgver`. The selected
asset must be `FreeCAD_<weekly-tag>-Linux-x86_64.AppImage`; missing or ambiguous
matches stop the update. New payloads are downloaded and hashed; a published
GitHub SHA-256 digest must match.

Downloads are temporary and discarded; no packages are built or uploaded. Review
upstream packaging compatibility and test locally.

See the [repository guide](../../README.md#local-build-and-installation) for the
shared local workflow and
[maintenance commands](../../README.md#recipe-checks-and-updates) for update
previews, applying recipe changes, and troubleshooting.
